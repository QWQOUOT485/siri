"""Read-only runtime firewall/profile inspection.

Firewall mutation belongs to the interactive setup script, after an explicit
user confirmation.  The agent process never changes the firewall.
"""

from __future__ import annotations

import json
import subprocess
import sys
from typing import Any

from .base import AdapterError


class WindowsFirewallInspector:
    RULE_NAME = "Siri Windows Agent"

    def _powershell_json(self, command: str) -> Any:
        if sys.platform != "win32":
            return None
        try:
            command = "$OutputEncoding = [System.Text.Encoding]::UTF8; [Console]::OutputEncoding = [System.Text.Encoding]::UTF8; " + command
            result = subprocess.run(
                ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", command],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=15,
                check=False,
                shell=False,
            )
            if not result.stdout.strip():
                return None
            return json.loads(result.stdout)
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            return None

    def inspect_network_profile(self) -> dict[str, Any]:
        data = self._powershell_json("Get-NetConnectionProfile | Select-Object Name,NetworkCategory,IPv4Connectivity | ConvertTo-Json -Compress")
        if data is None:
            return {"available": False, "profiles": [], "warning": "Could not inspect Windows network profiles"}
        return {"available": True, "profiles": data if isinstance(data, list) else [data]}

    def inspect_firewall_rule(self) -> dict[str, Any]:
        command = "Get-NetFirewallRule -DisplayName 'Siri Windows Agent' -ErrorAction SilentlyContinue | Select-Object DisplayName,Enabled,Profile,Direction,Action | ConvertTo-Json -Compress"
        data = self._powershell_json(command)
        if data is None:
            return {"available": True, "exists": False}
        return {"available": True, "exists": True, "rules": data if isinstance(data, list) else [data]}

    def create_private_rule(self, *args, **kwargs):
        raise AdapterError("Firewall changes are setup-only; run setup.ps1 after explicit confirmation")

    def remove_agent_rule(self, *args, **kwargs):
        raise AdapterError("Firewall changes are setup-only; run uninstall.ps1")
