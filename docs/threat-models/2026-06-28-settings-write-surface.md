# Threat Model — Startup-Hook Config Write Surface (B3 hook install)

**Status:** Active — covers the `install-hooks` command (Plan 2 Slice B3).
**Framework:** STRIDE (Tampering / Elevation of Privilege focus) on a file-write boundary.
**Scope:** `agent-config-sync install-hooks` writing `~/.claude/settings.json` (JSON)
**and** `~/.codex/config.toml` (TOML). Gemini is wired via the Gemini CLI's own
`hooks migrate` (no direct write by this tool).

---

## Why this needs its own model

This is the project's **only write outside the `config/targets.yaml` allowlist**.
`settings.json` holds `enabledPlugins`, `permissions`, and existing `hooks`.
Hook commands execute automatically at session start — a corrupted or attacker-
controlled entry is **arbitrary code execution at every launch**, and a clobbered
`permissions`/`enabledPlugins` block could silently disable security controls.

## Asset

- `~/.claude/settings.json` — plugin enablement, permissions, and the hook commands
  Claude Code runs on session lifecycle events.

## Trust boundary

`install-hooks` (repo code) → `settings.json` (Claude Code's runtime config),
outside the allowlist that bounds every other write in this tool.

## Threats & mitigations (code-mapped)

| ID | Threat (STRIDE) | Mitigation | Code pointer |
|----|-----------------|------------|--------------|
| S1 | **Tampering:** rewrite corrupts/drops `permissions`, `enabledPlugins`, or other hooks | Parse full JSON; mutate **only** `hooks.SessionStart` (key-addressed, never string-splice); preserve all other keys | `settingsedit.install_claude_hook` |
| S2 | **EoP:** an attacker-chosen command is installed as a startup hook | Installed command is a **fixed literal** (`agent-config-sync sense`), never derived from input | `cli.py` install-hooks handler |
| S3 | **Tampering:** duplicate/stacked hooks on repeated runs | **Idempotent** — exact command-string match; returns False without writing if present | `install_claude_hook` (existing-command check) |
| S4 | **DoS / corruption:** a malformed pre-existing `settings.json` is overwritten with garbage | Abort on parse failure **before any write** (`HookInstallError`), leaving the file untouched | `install_claude_hook` (json.loads guard) |
| S5 | **Recoverability:** a bad write loses the prior config | Back up to `.backups/settings/<stamp>/` before writing; atomic temp+replace | `install_claude_hook` (backup + os.replace) |

## Gemini / Codex notes

- **Gemini:** the hook is not hand-written; `gemini hooks migrate --from-claude`
  converts the Claude hook into Gemini's own `~/.gemini/settings.json`. The
  conversion is owned by the Gemini CLI (outside this tool's write surface).
- **Codex:** `codex_hooks` (a stable, default-on feature) is config-driven via
  `[[hooks.SessionStart]]` in `config.toml` — no CLI. `install_codex_hook` applies
  the **same STRIDE controls** as the Claude writer: parse with `tomllib` (abort on
  invalid TOML), idempotency by exact command match, append-only (preserves `notify`
  and all `[plugins.*]`), **re-validate the result with `tomllib` before writing**,
  reject command strings containing quotes/backslashes/newlines, and back up first.
  Verified live: `notify` (computer-use), plugins, and `model` preserved; result is
  valid TOML.

## Delta 2026-07-04 — sense hook output as AI context

The installed hook command is now `agent-config-sync sense`, whose stdout is
injected into the AI runtime's context at session start. That makes the hook
output an indirect-prompt-injection channel in principle. Controls:

| Threat | Mitigation | Code |
|---|---|---|
| Attacker-influenced text reaches the AI via sense output (Tampering) | Output is fixed deterministic phrasing; the only variable parts are grammar-validated skill names (`validate_skill_name`), runtime names from the allowlisted config, and destination paths already validated by `resolve_within`/`_validate_dest`. Free-text file content is never echoed | `sense.format_brief`, `validation.py`, `config.py` |
| AI acts on a finding without operator consent (Elevation of Privilege) | Every findings header instructs "Ask the operator before running any command below"; the projected instruction files carry the same rule; sense itself is read-only and holds no write authority | `sense.format_brief`, `_shared/core.md` |
| Gate error at sensing time crashes the session hook (Denial of Service) | Gate exceptions are converted to findings, never tracebacks | `sense.scan` |
| Hook replacement clobbers an operator's own hook (Tampering) | Superseded-command removal is exact-match only (byte-identical Codex block; JSON entries whose every command is superseded); edited entries are preserved | `settingsedit.install_claude_hook` / `install_codex_hook` |
| Scheduled watcher task executes attacker-modified script daily (EoP) | Task command is a fixed literal pointing at a version-controlled, reviewed script; the wrapper contains no mutating command and the Python cycle is read-only by construction (should-fail tested) | `scripts/sense-watcher.ps1`, `watcher.watch_once`, `tests/test_watcher.py` |
| MCP client (possibly prompt-injected) attempts mutation through `mcp-serve` (EoP) | Read-only by construction: the server module imports no mutating function; tool allowlist is fixed; regression test fails on any mutating import; stdio transport inherits the local-user boundary | `mcp_server.py`, `tests/test_mcp_server.py` |
| Forged pending.json steers the AI at session start (Tampering/injection) | Advisory-only by design: session hook always re-runs `sense` live; nothing consequential rides on the file alone (signing considered and rejected — TRADEOFFS) | `watcher.py`, ambient-automation spec |

## Residual risk

- The fixed hook command runs `agent-config-sync sense` at every session start; if
  the installed package or PATH is later compromised, that command runs with the
  user's privileges (same as any installed console script — not unique to this tool).
- Backup accumulation is bounded by the operator-invoked `prune-backups` command
  (dry-run by default; settings backups land under `.backups/settings/` and
  `.backups/codex-config/`, inside the pruning root). Pruning is intentional,
  not automatic — an operator who never runs it still accumulates snapshots.

*(Resolved since first written: `install-hooks --dry-run` now exists and prints
targets/commands without writing, and backup pruning is implemented — see
`cli.py` install-hooks/prune-backups handlers and `fsutil.prune_backups`.)*
