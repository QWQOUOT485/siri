# Migration Checklist

This document traces every requirement from the original specification ([SOURCE_SPEC.md](SOURCE_SPEC.md)) to its destination in the restructured documentation.

## Status Legend

- **Migrated** — Requirement faithfully transferred to destination file(s)
- **Superseded by #xxx** — Later revision replaces this requirement; revised version is migrated
- **Intentionally Duplicated** — Appears in multiple files (typically security invariants) via content or cross-reference

---

## Requirements #1–#100

| Source | Title | Destination | Status | Notes |
|--------|-------|-------------|--------|-------|
| #0 | GitHub / OSS research first | [SPEC.md](SPEC.md) §Dependencies, [AGENTS.md](../../AGENTS.md) §External Libraries | Migrated | — |
| #1 | Project Goal — Siri controls Windows PC | [SPEC.md](SPEC.md) §Project Goal, [README.md](../README.md) | Migrated | — |
| #2 | No public network solutions | [NETWORKING.md](NETWORKING.md) §No Public Network, [SECURITY.md](SECURITY.md) §LAN Security | Migrated | Intentionally Duplicated |
| #3 | Siri voice commands | [SPEC.md](SPEC.md) §Siri Usage Experience | Migrated | — |
| #4 | Auto-discover installed applications | [SPEC.md](SPEC.md) §Application Discovery | Migrated | — |
| #5 | Application Discovery sources | [SPEC.md](SPEC.md) §Application Discovery, [WINDOWS.md](WINDOWS.md) §Discovery Sources | Superseded by #103 | #103 adds Trusted/Metadata-only classification; both versions migrated |
| #6 | Don't scan entire hard drive | [SPEC.md](SPEC.md) §Application Discovery, [WINDOWS.md](WINDOWS.md) §Don't Scan Entire Hard Drive | Migrated | — |
| #7 | Application Catalog data structure | [SPEC.md](SPEC.md) §Application Catalog, [ARCHITECTURE.md](ARCHITECTURE.md) §Key Data Models | Superseded by #103 | #103 adds launch_source, launch_confidence, metadata_confidence fields |
| #8 | Name recognition / normalization | [SPEC.md](SPEC.md) §Name Recognition | Migrated | — |
| #9 | Chinese aliases | [SPEC.md](SPEC.md) §Chinese Aliases | Migrated | Full alias list preserved |
| #10 | Fuzzy search | [SPEC.md](SPEC.md) §Fuzzy Search | Migrated | — |
| #11 | Search priority order | [SPEC.md](SPEC.md) §Search Priority, [ARCHITECTURE.md](ARCHITECTURE.md) §Matcher | Migrated | — |
| #12 | Open app (open_app) | [SPEC.md](SPEC.md) §Open App | Migrated | — |
| #13 | Open app security requirements | [SECURITY.md](SECURITY.md) §Input Boundary, [SECURITY.md](SECURITY.md) §Trusted Execution Flow | Migrated | Superseded in detail by #104 |
| #14 | Close app (close_app) | [SPEC.md](SPEC.md) §Close App | Superseded by #105 | #105 adds Running Application Resolver detail |
| #15 | Process mapping | [SPEC.md](SPEC.md) §Process Mapping, [WINDOWS.md](WINDOWS.md) §Process Resolver | Superseded by #105 | #105 strengthens process resolution requirements |
| #16 | Windows built-in programs | [SPEC.md](SPEC.md) §Windows Built-in Programs | Superseded by #106 | #106 adds system_apps mapping concept |
| #17 | Websites (open_website) | [SPEC.md](SPEC.md) §Websites, [SECURITY.md](SECURITY.md) §Website Security | Migrated | — |
| #18 | System default browser | [SPEC.md](SPEC.md) §Websites | Migrated | — |
| #19 | Media control | [SPEC.md](SPEC.md) §Media Control, [WINDOWS.md](WINDOWS.md) §Media Control | Migrated | — |
| #20 | Volume control | [SPEC.md](SPEC.md) §Volume Control, [WINDOWS.md](WINDOWS.md) §Volume Control | Migrated | — |
| #21 | Lock Windows | [SPEC.md](SPEC.md) §Lock, [WINDOWS.md](WINDOWS.md) §Lock | Migrated | — |
| #22 | Shutdown two-step confirmation | [SPEC.md](SPEC.md) §Shutdown, [SECURITY.md](SECURITY.md) §Shutdown Two-Step, [API.md](API.md) §Shutdown Flow | Migrated | Intentionally Duplicated across SPEC/SECURITY/API |
| #23 | Shutdown token replay prevention | [SECURITY.md](SECURITY.md) §Shutdown Two-Step Confirmation | Migrated | — |
| #24 | Local Network Only (FastAPI) | [NETWORKING.md](NETWORKING.md) §FastAPI Server | Migrated | — |
| #25 | Windows Firewall | [NETWORKING.md](NETWORKING.md) §Windows Firewall, [WINDOWS.md](WINDOWS.md) §Firewall, [SECURITY.md](SECURITY.md) §Firewall Security | Superseded by #107 | #107 clarifies inspect vs create responsibility |
| #26 | Firewall source scope / multi-subnet | [NETWORKING.md](NETWORKING.md) §Multi-Subnet, [WINDOWS.md](WINDOWS.md) §Firewall | Migrated | — |
| #27 | LAN network situation | [NETWORKING.md](NETWORKING.md) §Different Wi-Fi Does NOT Mean Can't Connect | Migrated | — |
| #28 | Potential connection failure causes | [NETWORKING.md](NETWORKING.md) §Potential Connection Issues | Migrated | — |
| #29 | Windows IP (hostname / fixed IP) | [NETWORKING.md](NETWORKING.md) §Windows IP Configuration | Migrated | — |
| #30 | Optional LAN Discovery (mDNS) | [NETWORKING.md](NETWORKING.md) §Optional LAN Discovery | Migrated | — |
| #31 | Authentication requirement | [SECURITY.md](SECURITY.md) §Authentication | Migrated | — |
| #32 | API Key storage | [SECURITY.md](SECURITY.md) §Authentication | Migrated | — |
| #33 | iPhone Shortcut authentication | [SECURITY.md](SECURITY.md) §Authentication, [SIRI_SHORTCUT.md](../features/siri_shortcut/SIRI_SHORTCUT.md) | Migrated | — |
| #34 | HTTP / HTTPS | [NETWORKING.md](NETWORKING.md) §HTTP vs HTTPS | Migrated | — |
| #35 | API endpoints list | [API.md](API.md) | Migrated | — |
| #36 | /health | [API.md](API.md) §GET /health, [SECURITY.md](SECURITY.md) §/health Endpoint Security | Migrated | — |
| #37 | /apps | [API.md](API.md) §GET /apps, [SECURITY.md](SECURITY.md) §API Response Security | Migrated | — |
| #38 | /apps/search | [API.md](API.md) §POST /apps/search | Migrated | — |
| #39 | /apps/refresh | [API.md](API.md) §POST /apps/refresh, [SPEC.md](SPEC.md) §App Refresh | Migrated | — |
| #40 | /action | [API.md](API.md) §POST /action | Migrated | — |
| #41 | /command | [API.md](API.md) §POST /command | Migrated | — |
| #42 | Rule-based parser, no LLM | [SPEC.md](SPEC.md) §Command Parser | Migrated | — |
| #43 | Media phrases (Chinese) | [SPEC.md](SPEC.md) §Media Phrases | Migrated | Full phrase list preserved |
| #44 | Volume phrases (Chinese) | [SPEC.md](SPEC.md) §Volume Phrases | Migrated | Full phrase list preserved |
| #45 | System phrases (Chinese) | [SPEC.md](SPEC.md) §System Phrases | Migrated | Full phrase list preserved |
| #46 | English commands | [SPEC.md](SPEC.md) §English Commands | Migrated | Full command list preserved |
| #47 | Parser security | [SECURITY.md](SECURITY.md) §Action Schema Security | Migrated | — |
| #48 | Malicious input handling | [SECURITY.md](SECURITY.md) §Malicious Input Handling | Migrated | — |
| #49 | Absolute prohibition of Remote Shell | [SECURITY.md](SECURITY.md) §Remote Execution Prohibition | Migrated | Most important security invariant |
| #50 | subprocess safety | [SECURITY.md](SECURITY.md) §subprocess Safety | Migrated | — |
| #51 | Path safety | [SECURITY.md](SECURITY.md) §Input Boundary | Migrated | — |
| #52 | Website security | [SECURITY.md](SECURITY.md) §Website Security | Migrated | — |
| #53 | Configuration file | [SPEC.md](SPEC.md) §Configuration | Migrated | — |
| #54 | Custom aliases in config | [SPEC.md](SPEC.md) §Custom Aliases | Migrated | — |
| #55 | App cache | [SPEC.md](SPEC.md) §App Cache, [WINDOWS.md](WINDOWS.md) §Runtime Cache | Migrated | — |
| #56 | Auto refresh | [SPEC.md](SPEC.md) §Auto Refresh | Migrated | — |
| #57 | setup.ps1 | [WINDOWS.md](WINDOWS.md) §Setup Script | Migrated | All 14 steps preserved |
| #58 | Windows Firewall setup | [WINDOWS.md](WINDOWS.md) §Firewall Handling | Superseded by #107 | #107 clarifies responsibility separation |
| #59 | start.bat | [WINDOWS.md](WINDOWS.md) §Start Script | Migrated | — |
| #60 | Stop Agent | [WINDOWS.md](WINDOWS.md) §Stop | Migrated | — |
| #61 | Windows auto-start | [WINDOWS.md](WINDOWS.md) §Auto-Start | Superseded by #102 | #102 specifies Task Scheduler only |
| #62 | System tray (nice-to-have) | [SPEC.md](SPEC.md) §System Tray | Migrated | — |
| #63 | Status UI (optional) | [SPEC.md](SPEC.md) §Status UI | Migrated | — |
| #64 | iPhone Shortcut setup guide | [SIRI_SHORTCUT.md](../features/siri_shortcut/SIRI_SHORTCUT.md) §Shortcut Setup | Migrated | — |
| #65 | iOS Shortcut simplicity | [SIRI_SHORTCUT.md](../features/siri_shortcut/SIRI_SHORTCUT.md) §Keep It Simple | Migrated | — |
| #66 | Apple Local Network Permission | [SIRI_SHORTCUT.md](../features/siri_shortcut/SIRI_SHORTCUT.md) §Local Network Permission | Migrated | — |
| #67 | Siri response messages | [SPEC.md](SPEC.md) §Siri Responses, [SIRI_SHORTCUT.md](../features/siri_shortcut/SIRI_SHORTCUT.md) | Migrated | — |
| #68 | Shutdown Shortcut flow | [SIRI_SHORTCUT.md](../features/siri_shortcut/SIRI_SHORTCUT.md) §Shutdown Confirmation, [API.md](API.md) §Shutdown Flow | Migrated | — |
| #69 | API response schema | [API.md](API.md) §Response Schema | Migrated | — |
| #70 | Error handling | [SPEC.md](SPEC.md) §Error Handling, [API.md](API.md) §Error Schema | Migrated | — |
| #71 | No stack trace to iPhone | [SECURITY.md](SECURITY.md) §Stack Trace Security | Migrated | — |
| #72 | Logging | [SECURITY.md](SECURITY.md) §Logging Security | Migrated | — |
| #73 | Rate limiting | [API.md](API.md) §Rate Limiting | Superseded by #108 | #108 clarifies placement in infrastructure layer |
| #74 | Replay / brute force protection | [SECURITY.md](SECURITY.md) §Authentication | Migrated | — |
| #75 | Dependencies | [SPEC.md](SPEC.md) §Dependencies | Migrated | — |
| #76 | Architecture / project structure | [ARCHITECTURE.md](ARCHITECTURE.md) §Directory Structure | Superseded by v2 appendix | v2 directory structure used |
| #77 | Tests (pytest) | [TESTING.md](TESTING.md) §Unit Tests | Superseded by #110 | #110 adds integration test category |
| #78 | Tests must not operate real computer | [TESTING.md](TESTING.md) §Unit Tests | Migrated | — |
| #79 | Security tests | [SECURITY.md](SECURITY.md) §Security Test Requirements, [TESTING.md](TESTING.md) §Security Tests | Migrated | Intentionally Duplicated |
| #80 | No shell=True | [SECURITY.md](SECURITY.md) §subprocess Safety | Migrated | — |
| #81 | README for non-engineers | [README.md](../README.md) | Migrated | Written in 繁體中文 |
| #82 | README required contents | [README.md](../README.md) | Migrated | All items included |
| #83 | Network health test | [NETWORKING.md](NETWORKING.md) §Network Health Test, [README.md](../README.md) | Migrated | — |
| #84 | Cross-floor troubleshooting | [NETWORKING.md](NETWORKING.md) §Cross-Floor Troubleshooting, [README.md](../README.md) | Migrated | — |
| #85 | Different subnet support | [NETWORKING.md](NETWORKING.md) §Multi-Subnet | Migrated | — |
| #86 | App refresh methods | [SPEC.md](SPEC.md) §App Refresh | Migrated | — |
| #87 | Portable app / manual_apps | [SPEC.md](SPEC.md) §Portable Apps, [SECURITY.md](SECURITY.md) §Manual Apps Security, [WINDOWS.md](WINDOWS.md) §Manual Apps | Migrated | Intentionally Duplicated (product + security + platform) |
| #88 | Manual apps validation | [SECURITY.md](SECURITY.md) §Manual Apps Security, [WINDOWS.md](WINDOWS.md) §Manual Apps | Migrated | — |
| #89 | App discovery diagnostics | [WINDOWS.md](WINDOWS.md) §App Discovery Diagnostics | Migrated | — |
| #90 | Version / GET /info | [SPEC.md](SPEC.md) §Version, [API.md](API.md) §GET /info | Migrated | — |
| #91 | .gitignore | [SPEC.md](SPEC.md) §Git | Migrated | — |
| #92 | requirements.txt | [SPEC.md](SPEC.md) §Dependencies | Migrated | — |
| #93 | GitHub OSS utilization | [SPEC.md](SPEC.md) §Dependencies, [AGENTS.md](../../AGENTS.md) §External Libraries | Migrated | — |
| #94 | No AI/LLM for v1 | [SPEC.md](SPEC.md) §Core Features / Local AI | Superseded | Superseded by the accepted 2026-09-18 product decision: V1 may use guarded Local AI under SECURITY.md constraints |
| #95 | Future extensibility | [SPEC.md](SPEC.md) §Future Extensibility | Migrated | — |
| #96 | Most important security baseline | [SECURITY.md](SECURITY.md) §Trusted Execution Flow | Superseded by #104 | #104 concretizes the data flow |
| #97 | Final user experience | [SPEC.md](SPEC.md) §User Experience, [README.md](../README.md) | Migrated | — |
| #98 | Self-verification after coding | [TASKS.md](../../TASKS.md) §Definition of Done | Migrated | — |
| #99 | Don't leave TODO | [AGENTS.md](../../AGENTS.md), [SPEC.md](SPEC.md) §Dependencies | Migrated | — |
| #100 | Final response format | [SPEC.md](SPEC.md) | Migrated | Applies to development workflow |

---

## Architecture Review Revisions #101–#111

| Source | Title | Destination | Status | Notes |
|--------|-------|-------------|--------|-------|
| #101 | Interactive User Session | [WINDOWS.md](WINDOWS.md) §Interactive Desktop Session, [ARCHITECTURE.md](ARCHITECTURE.md) §Layer Architecture | Migrated | Mandatory architectural requirement |
| #102 | Task Scheduler At log on | [WINDOWS.md](WINDOWS.md) §Task Scheduler | Migrated | Supersedes #61 (Startup Folder removed from v1) |
| #103 | Trusted Launch Source vs Metadata-only Source | [ARCHITECTURE.md](ARCHITECTURE.md) §Discovery Source Classification, [WINDOWS.md](WINDOWS.md) §Discovery Sources | Migrated | Supersedes/concretizes #5 |
| #104 | Secure launch data flow | [SECURITY.md](SECURITY.md) §Trusted Execution Flow, [ARCHITECTURE.md](ARCHITECTURE.md) | Migrated | Concretizes #13 + #96 |
| #105 | Running Application Resolver | [ARCHITECTURE.md](ARCHITECTURE.md) §Running Application Resolver, [SPEC.md](SPEC.md) §Close App, [WINDOWS.md](WINDOWS.md) §Process Resolver | Migrated | Supersedes/strengthens #14-#15. Force close trigger phrases preserved in SPEC.md |
| #106 | system_apps mapping | [ARCHITECTURE.md](ARCHITECTURE.md) §system_apps Mapping, [WINDOWS.md](WINDOWS.md) §system_apps Mapping | Migrated | Supersedes/concretizes #16 |
| #107 | Firewall inspect vs create separation | [ARCHITECTURE.md](ARCHITECTURE.md) §Firewall Responsibility, [WINDOWS.md](WINDOWS.md) §Firewall, [SECURITY.md](SECURITY.md) §Firewall Security | Migrated | Concretizes #25, #58 |
| #108 | Rate limiter in infrastructure layer | [ARCHITECTURE.md](ARCHITECTURE.md) §Rate Limiter Placement, [API.md](API.md) §Rate Limiting | Migrated | Concretizes #73 |
| #109 | All adapters target interactive user | [WINDOWS.md](WINDOWS.md) §Interactive Desktop Session | Migrated | Extends #101 to all adapters |
| #110 | Unit / Integration Test separation | [TESTING.md](TESTING.md) | Migrated | Extends #77-#78 with integration test category |
| #111 | Review scope declaration | All files | Migrated | Confirms #101-#110 don't change core #1-#100 requirements |

---

## Priority Section

| Source | Destination | Status | Notes |
|--------|-------------|--------|-------|
| Priority order (安全 > 能正常使用 > Siri Shortcut 簡單 > 自動辨識已安裝程式 > LAN 跨 Wi-Fi/subnet > 穩定 > 容易安裝 > 容易維護 > UI 漂亮) | [SPEC.md](SPEC.md) §Priority | Migrated | Full priority list preserved |
| "不要為了漂亮 UI 犧牲核心功能" | [SPEC.md](SPEC.md) §Priority | Migrated | — |

---

## v2 Architecture Appendix

| Source | Destination | Status | Notes |
|--------|-------------|--------|-------|
| Layer diagram (API → Infrastructure → Service → Domain → Windows Adapter → Interactive Session → Windows) | [ARCHITECTURE.md](ARCHITECTURE.md) §Layer Architecture | Migrated | — |
| Directory structure (v2) | [ARCHITECTURE.md](ARCHITECTURE.md) §Directory Structure | Migrated | Full structure preserved |
| 10 Key Design Decisions (v2) | [ARCHITECTURE.md](ARCHITECTURE.md) §Key Design Decisions | Migrated | All 10 decisions preserved |
| "Benefits for users" section | [ARCHITECTURE.md](ARCHITECTURE.md) | Migrated | — |

---

## Summary

- **Total requirements**: 112 (§0–§111) + Priority section + v2 Architecture appendix
- **Migrated**: All
- **Superseded by later revision/product decision**: #5→#103, #7→#103, #13→#104, #14→#105, #15→#105, #16→#106, #25→#107, #58→#107, #61→#102, #73→#108, #76→v2, #77→#110, #94→2026-09-18 guarded Local AI product decision, #96→#104 (all active replacements migrated)
- **Intentionally Duplicated**: #2, #22, #79, #87 (security invariants preserved across relevant files via content or cross-reference)
- **Omitted**: None
- **Summarized away**: None
