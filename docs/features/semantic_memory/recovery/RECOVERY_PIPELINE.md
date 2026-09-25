# Recovery Pipeline

## 1. Eligibility

Local Semantic Recovery is initially limited to Spotify named-track interpretation.

It does not process:

- shutdown / confirmation
- force-close
- firewall
- system administration
- generic app execution
- Windows master-volume commands
- Spotify clarification ordinal selection

Non-Spotify deterministic commands keep their existing path.

## 2. Entity normalization

Keep the original text and derive comparison forms rather than destructively replacing it.

Recommended deterministic forms:

```text
raw
canonical_text
compact_text
chinese_canonical
```

Operations may include:

- Unicode NFKC
- case folding
- trimming/collapsing whitespace
- bounded punctuation normalization
- punctuation-stripped compact comparison key
- existing Traditional/Simplified canonicalization

Example:

```text
Sad Overlxrd
→ sad overlxrd
→ sadoverlxrd

SASIOVERLXRD
→ sasioverlxrd
```

Do not reject legitimate one-character entities with a blanket minimum-length rule.

## 3. Exact confirmed alias fast path

Before expensive recovery, query the in-memory confirmed-alias index.

Requirements:

```text
exact normalized alias
AND trust_state = confirmed
AND active
AND not conflicted
```

Only this Phase 1 memory path may automatically canonicalize the user-stated entity before rerunning the normal Spotify resolver.

## 4. Primary Spotify resolution

After any exact confirmed canonicalization, use the normal Spotify path:

```text
Spotify Search
→ Live/studio filtering
→ deterministic identity/matching
→ candidate ranking
→ ambiguity decision
```

A safe result ends recovery.

## 5. RapidFuzz recovery

When the primary resolver remains unresolved:

```text
normalized alias
→ RapidFuzz top-k local aliases
→ RecoveryCandidateEvidence
```

Phase 1 is **candidate-only**.

A fuzzy result must not:

- silently replace the artist
- produce a trusted provider ID
- directly retry playback as a confirmed identity
- promote an alias to confirmed

It may help populate or order trusted clarification candidates.

No production threshold is assumed from theory. Thresholds must come from the fixed fixture corpus.

## 6. Track-first evidence

When track+artist resolution fails and the track text is sufficiently grounded, a bounded track-only Spotify search may be used as independent deterministic evidence.

Example:

```text
track = 死亡是生命的終點
heard artist = sad overlxrd
```

Track-first results are server-owned Spotify results. In Phase 1/1B they remain candidate evidence only.

They must not silently canonicalize an artist. If multiple plausible artists remain, use clarification.

Additional calls must be bounded and 429-aware.

## 7. Clarification

Reuse the existing `SpotifyClarificationStore`.

Do not create another token system.

Useful fuzzy/track-first candidates are converted into a server-owned candidate set, then existing clarification rules apply:

- short TTL
- max 3 candidates
- bounded failed attempts
- at most one successful concurrent selection
- client cannot inject Spotify URI/track ID

## 8. Learning point

The automatic confirmation event occurs only after:

```text
observed ASR alias
+ trusted server-owned clarification candidates
+ user explicitly selected one
+ playback succeeded
```

Only then may `MemoryLearner` promote the mapping to `confirmed`.

If playback fails because of network/device/401/403/429/etc., do not confirm the alias.

## 9. Future vector retrieval

Vector retrieval is not Phase 1.

If later introduced:

```text
user-authored/Siri-transcribed utterance
→ local embedding
→ similar user utterance memories
→ candidate evidence only
```

Do not embed Spotify catalog metadata.

The first vector rollout must be shadow-only and demonstrate incremental value over lexical retrieval before it can affect clarification candidates.

## 10. Local AI semantic retry

AI stays last in the ladder and follows the existing gated design:

```text
original utterance
→ deterministic eligibility
→ RawAIIntent
→ strict schema
→ SemanticGrounder(original utterance)
→ GroundedAIIntent
→ AIPolicyGate
→ ValidatedAction
→ deterministic Spotify resolver
```

AI may propose grounded track/artist/album text. It may not:

- choose Spotify candidate IDs/URIs
- rank Spotify search candidates
- consume/select clarification candidates
- play media
- confirm aliases

An AI-grounded user string may still pass through the exact confirmed alias lookup before the deterministic Spotify resolver.

## 11. Decision tiers

```text
Tier A: exact confirmed alias, no conflict
→ automatic canonicalization allowed

Tier B: fuzzy and/or track-first support
→ candidate evidence only

Tier C: competing credible mappings
→ clarification

Tier D: weak local evidence
→ future vector or AI semantic retry

Tier E: still unresolved
→ safe failure
```

## 12. Performance ordering

Use the cheapest/highest-trust path first:

```text
normalize
→ exact RAM alias
→ normal Spotify resolver
→ local fuzzy evidence
→ bounded track-first evidence
→ future vector
→ AI
```

Do not run vector/AI on requests already resolved by earlier stages.
