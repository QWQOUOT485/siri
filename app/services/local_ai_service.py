"""Gated Local AI semantic-retry orchestration."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from pydantic import ValidationError

from app.adapters.local_ai import LMStudioLocalAIAdapter, LocalAIAdapter, LocalAITransportError
from app.domain.actions import ParsedCommand, ValidatedAction
from app.domain.local_ai import RawAIIntent
from app.infrastructure.config import AppConfig

from .ai_eligibility import SemanticRetryEligibilityGate
from .ai_policy import AIPolicyGate
from .semantic_grounder import SemanticGrounder


@dataclass(frozen=True)
class LocalAIResult:
    """Safe pipeline outcome; raw model content is deliberately absent."""

    status: str
    reason: str
    action: ValidatedAction | None = None
    model_id: str | None = None
    latency_ms: float | None = None

    @property
    def execution_allowed(self) -> bool:
        return self.status == "accepted_fallback" and self.action is not None


class LocalAIService:
    """Keep transport, grounding, and policy behind one small retry interface."""

    def __init__(
        self,
        *,
        mode: str = "off",
        adapter: LocalAIAdapter | None = None,
        fallback_approved: bool = False,
        eligibility_gate: SemanticRetryEligibilityGate | None = None,
        grounder: SemanticGrounder | None = None,
        policy_gate: AIPolicyGate | None = None,
        logger: Any | None = None,
    ) -> None:
        self.mode = mode if mode in {"off", "shadow", "fallback"} else "off"
        self.adapter = adapter
        self.fallback_approved = bool(fallback_approved)
        self.eligibility_gate = eligibility_gate or SemanticRetryEligibilityGate()
        self.grounder = grounder or SemanticGrounder()
        self.policy_gate = policy_gate or AIPolicyGate()
        self.logger = logger

    @classmethod
    def from_config(cls, config: AppConfig, *, logger: Any | None = None) -> "LocalAIService":
        if not config.local_ai_enabled or config.local_ai_mode == "off":
            return cls(mode="off", logger=logger)
        try:
            adapter = LMStudioLocalAIAdapter(
                config.local_ai_base_url,
                config.local_ai_model,
                timeout_seconds=config.local_ai_timeout_seconds,
                max_response_bytes=config.local_ai_max_response_bytes,
            )
        except ValueError:
            if logger is not None:
                logger.warning("local_ai status=disabled reason=configuration_rejected")
            return cls(mode=config.local_ai_mode, logger=logger)
        return cls(
            mode=config.local_ai_mode,
            adapter=adapter,
            fallback_approved=config.local_ai_fallback_approved,
            logger=logger,
        )

    def retry(
        self,
        original_text: str,
        parsed: ParsedCommand,
        *,
        deterministic_success: bool = False,
        deterministic_error_code: str | None = None,
        clarification_token_present: bool = False,
    ) -> LocalAIResult:
        if self.mode == "off":
            return self._finish("disabled", "mode_off")

        eligibility = self.eligibility_gate.evaluate(
            original_text,
            parsed,
            deterministic_success=deterministic_success,
            deterministic_error_code=deterministic_error_code,
            clarification_token_present=clarification_token_present,
        )
        if not eligibility.eligible:
            return self._finish("ineligible", eligibility.reason)
        if self.mode == "fallback" and not self.fallback_approved:
            return self._finish("fallback_unapproved", "promotion_gate_required")
        if self.adapter is None:
            return self._finish("unavailable", "adapter_not_configured")

        try:
            response = self.adapter.infer(original_text)
        except LocalAITransportError as exc:
            return self._finish("transport_error", exc.reason)
        except Exception:
            return self._finish("transport_error", "adapter_error")

        try:
            payload = json.loads(response.content)
            raw = RawAIIntent.model_validate(payload, strict=True)
        except (json.JSONDecodeError, TypeError, ValidationError):
            return self._finish("schema_rejected", "strict_schema_rejected", response.model_id, response.latency_ms)

        grounded = self.grounder.ground(original_text, raw)
        if not grounded.accepted:
            return self._finish("grounding_rejected", grounded.reason, response.model_id, response.latency_ms)

        policy = self.policy_gate.apply(grounded.grounded)
        if not policy.accepted:
            return self._finish("policy_rejected", policy.reason, response.model_id, response.latency_ms)
        if policy.action is None:
            return self._finish("accepted_unknown", policy.reason, response.model_id, response.latency_ms)

        if self.mode == "fallback" and self.fallback_approved:
            return self._finish("accepted_fallback", policy.reason, response.model_id, response.latency_ms, policy.action)
        return self._finish("shadow_accepted", policy.reason, response.model_id, response.latency_ms)

    def status_view(self) -> dict[str, Any]:
        """Return non-secret diagnostics suitable for authenticated `/info`."""

        return {
            "mode": self.mode,
            "adapter_configured": self.adapter is not None,
            "fallback_approved": self.fallback_approved,
        }

    def _finish(
        self,
        status: str,
        reason: str,
        model_id: str | None = None,
        latency_ms: float | None = None,
        action: ValidatedAction | None = None,
    ) -> LocalAIResult:
        result = LocalAIResult(status, reason, action, model_id, latency_ms)
        if self.logger is not None:
            self.logger.info(
                "local_ai status=%s reason=%s model=%s latency_ms=%s",
                status,
                reason,
                model_id or "none",
                f"{latency_ms:.2f}" if latency_ms is not None else "none",
            )
        return result
