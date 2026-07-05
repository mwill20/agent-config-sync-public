# Lesson Index - agent-config-sync

A hands-on curriculum for the `agent-config-sync` codebase. Each lesson maps the
engineering concept to security operations, implementation, and AI-runtime risk.

Validation command for exercises:

```bash
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q -p no:cacheprovider
```

| Lesson | Title | File | Status | Required |
|--------|-------|------|--------|----------|
| 00 | System Overview - The Projector | Lesson00_System_Overview.md | Complete | Required |
| 01 | The Render Core - Deterministic Projection | Lesson01_Render_Core.md | Complete | Required |
| 02 | The Allowlist - Write Trust Boundary | Lesson02_Allowlist_Config.md | Complete | Required |
| 03 | Deterministic Gates - Secret & Neutral-Language Lints | Lesson03_Deterministic_Gates.md | Complete | Required |
| 04 | Atomic Writes & Drift Hashing | Lesson04_Fsutil_State.md | Complete | Required |
| 05 | Forward Projection & the Drift Guard | Lesson05_Project_DriftGuard.md | Complete | Required |
| 06 | Skills Projection & Enrollment | Lesson06_Skills_Enroll.md | Complete | Required |
| 07 | Capture-from-Chat - Untrusted Input to Source | Lesson07_Capture.md | Complete | Required |
| 08 | Reverse Promote & 3-Way Conflicts | Lesson08_Promote.md | Complete | Required |
| 09 | The Allowlist Exception - Writing settings.json | Lesson09_Settings_Hooks.md | Complete | Required |
| 10 | The CLI Surface & doctor | Lesson10_CLI_Doctor.md | Complete | Optional |
| 11 | Operational Hardening - Locks, Backup Pruning, Supply-Chain Pins, and Hermetic E2E | Lesson11_Operational_Hardening.md | Complete | Optional |
| 12 | The Control Tower - Operating the Tool Day to Day | Lesson12_Operator_Guide.md | Complete | Required |
| 13 | The Night Patrol - Building an Ambient Agent Safely | Lesson13_Ambient_Watcher.md | Complete | Required |
| 14 | The Front Desk Window - A Read-Only MCP Server | Lesson14_MCP_Status_Server.md | Complete | Optional |

Read Lesson 00 first. Lessons 01-11 follow the data flow: render, allowlist,
gates, writes/state, projection, skills/enroll, capture, promote, settings
exception, CLI, and operational hardening. Lesson 12 is the operator's
"how to use this tool" guide; read it first if you only want to run the tool
rather than understand its internals.