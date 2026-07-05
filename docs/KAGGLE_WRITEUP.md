# agent-config-sync: One Brain for Three AI Agents

## Subtitle: A security-first sync system where Claude, Codex, and Gemini share one source of truth, watch it for drift, and audit each other

## The problem

I run three AI coding assistants side by side: Claude Code, Codex, and Gemini with Antigravity. Each one reads its own global instruction file and its own folder of skills. That created a problem I recognized immediately from my day job as a security analyst: configuration drift. Teach Claude a new standard and Codex never hears about it. Improve a skill inside Gemini and the other two keep the stale version. Within weeks, my three assistants were following three different rulebooks, and I had no way to know which one had drifted or when.

This is the same failure mode as maintaining the same detection rule in two SIEMs by hand. Security teams solved it decades ago with a golden source, controlled deployment, and integrity monitoring. Nobody had applied that discipline to the instruction files and skills that steer AI agents. So I built it.

## Why agents

Agents are both the problem and the solution here. The problem is agent-shaped: instruction files are effectively standing system prompts, and skills are standing capabilities, so drift between them changes agent behavior silently. The solution is agent-shaped too, in three ways.

First, every AI session becomes a participant. A session-start hook in all three runtimes runs a sensing command, and the agent reading its output explains what changed and asks me before acting. Second, an ambient agent runs when no session is open: a daily watcher that checks for drift in the background and notifies me, a concept I took directly from this course and applied the same week I learned it. Third, the agents police each other. During the build, Codex ran a full security audit of the tool through a skill that the tool itself had delivered to Codex, and found two real enforcement gaps that I then fixed. The system that syncs the agents was audited by the agents it syncs.

## What it does

agent-config-sync is a Python CLI that treats one git repository as the single source of truth for AI configuration. A neutral standards file plus small per-runtime overlays generate each assistant's instruction file. Skills are enrolled one at a time through deterministic security gates, then projected to every runtime with a per-runtime adapter that translates neutral wording into that runtime's tool vocabulary.

The daily loop looks like this. I open any assistant and the hook tells me, in one line, whether anything changed: the source moved ahead, a runtime copy was edited locally, or a new unmanaged skill appeared. The assistant names the exact resolution command and asks before running it. Between sessions, a scheduled watcher does the same check once a day and raises a Windows notification, with a heartbeat design so silence means the watcher itself is broken rather than everything being fine. When something needs fixing, an operator-invoked proposal agent drafts the cleanup, such as a neutralized skill body ready for enrollment, and I approve or reject it.

## Architecture

```
              SOURCE OF TRUTH (git repo)
   _shared/core.md + overlays/<vendor>.md + skills/<name>/
                        |
        deterministic gates on every write path:
        secret scan | neutral-language lint | path allowlist | drift guard
                        |
                     project
                        v
   ~/.claude          ~/.codex          ~/.gemini
   CLAUDE.md          AGENTS.md         GEMINI.md
   + skills           + skills          + skills
        |                 |                 |
   session hook      session hook      session hook
   (sense: what changed, exact fix, ask the operator first)
                        ^
     daily ambient watcher (read-only, heartbeat, notification)
                        ^
     MCP server (read-only sense/check/status for any MCP client)
                        ^
     draft-proposals agent (operator-invoked, proposals only)
```

The design principle throughout: agents propose, deterministic code decides, the human authorizes. A language model never holds write authority anywhere in this system. Every consequential write passes rule-based gates that no amount of prompt injection can talk its way past, because they are regular expressions and path checks, not model judgment.

## The security story

This is a security tool for agent infrastructure, and the threat model drove the design. The projected files are system-prompt-adjacent input for three autonomous agents, which makes the whole pipeline an indirect prompt injection amplifier: poison the source once and three agents ingest it forever. The controls, all code-mapped in four STRIDE threat model documents in the repo:

* A secret scanner and a vendor-neutral language lint run at enrollment and again at projection time, so even a direct edit to the source cannot fan out ungated.
* A write allowlist and resolved-path containment bound every destination the tool can touch.
* A drift guard hashes everything the tool writes; an out-of-band edit is refused, never silently overwritten, and a blanket force across multiple drifted targets is rejected so one override cannot cause collateral damage.
* Every overwrite is backed up first and recorded in an append-only audit log.
* The ambient watcher and the MCP server are read-only by construction: no mutating function is importable from either module, and a regression test fails the build if anyone ever adds one.
* The proposal agent treats every runtime-edited file as untrusted input. Its eval dataset includes a case where hidden instructions inside an edit tell the agent to write to the master standards file. Passing requires quoting the injection as evidence and refusing to obey it. The agent passed all twelve property checks, and its own system prompt is a version-controlled managed skill, screened by the same gates as everything else.

One decision worth calling out because we rejected a control: the watcher's pending-findings file carries no cryptographic signature. Analysis showed any local process able to forge the file could also read any locally derivable key, so a signature would be theater. The honest control is architectural: the file is advisory only, and every session re-runs the live check. The tradeoffs document records this reasoning so a future maintainer does not reintroduce the theater.

## The build: agents auditing agents

The build itself demonstrates multi-agent collaboration in a way I did not plan and could not have scripted. Claude Code did the primary engineering. Antigravity validated the reverse-promotion path and fixed the Gemini skills directory location, then installed the hooks on its own side. Codex, running the repo-standards audit skill that agent-config-sync had projected into it, independently reproduced the test suite and found two genuine enforcement gaps: skill bodies were linted at enrollment but not at projection, and slash commands wrapped in backticks slipped past the language gate. Both were fixed with regression tests the same day, and Codex's second audit pass came back clean.

The live verification followed detection-engineering practice: plant a known change, verify the tool names exactly that change, and confirm the agent asks before acting. In one drill the safety layer even blocked me, the assistant, from running a discard command before the human had actually typed yes. The confirm gate held against its own builder, which is precisely what it is for.

Course concepts landed directly in the build. The ambient agent pattern from the course became the daily watcher, staged deliberately: deterministic patrol first, language model tier gated behind two weeks of proven operation, shipped early only in its operator-supervised form after passing its eval. Agent skills are the core payload: the tool manages 36 of them in production, including the full Google Agents CLI skill suite for ADK development, each neutralized and distributed across all three runtimes. The MCP server exposes sync state to any MCP client through a hand-rolled protocol subset with zero new dependencies, keeping the supply chain fully pinned.

## Course concepts demonstrated

| Concept | Where |
|---|---|
| Agent skills (Agents CLI) | The core of the project: 36 managed skills enrolled, neutralized, and projected across three runtimes, including the google-agents-cli ADK suite; overlap detector for redundancy triage |
| MCP server | `src/agent_config_sync/mcp_server.py`: read-only stdio server exposing sense, check, and status tools; dependency-free JSON-RPC subset; regression test enforces that no mutating verb can ever be exposed |
| Security features | Deterministic gates on every write path, four STRIDE threat models with code-mapped mitigations, prompt injection eval dataset, audit logging, drift refusal, backup-before-overwrite |
| Antigravity | Active build participant: validated promote, fixed the Gemini skills path, installed hooks; receives and runs managed skills daily |
| Ambient agent | Tier 2 daily watcher with heartbeat and human-in-the-loop retention; Tier 3 proposal drafter, operator-invoked, eval-gated |

## Results, all verifiable in the repo

* 217 automated tests passing, with at least one should-fail case on every consequential path, including gate bypass attempts, drift refusal, injection handling, and the no-mutation guarantees.
* Live verification drills in all three runtimes, documented with method and proof rationale in the evaluation log.
* An independent audit by a second AI (Codex) that found real gaps, followed by a clean second pass.
* First production run of the sensing feature surfaced 12 unmanaged skills across two runtimes that no one had noticed, all triaged and enrolled through the gates the same day.
* The proposal agent passed 12 of 12 eval checks, including the injection and credential-smuggling traps.
* Fourteen hands-on lessons teaching the system's engineering and security decisions, written against the real code.

## Try it

The repository is public under the MIT license: https://github.com/mwill20/agent-config-sync-public

Setup is in the README quickstart: clone, create a venv, `pip install -e ".[dev]"`, then run `agent-config-sync check` and `agent-config-sync project --dry-run` to see the projection plan without writing anything. The test suite runs with one command and the evaluation log shows what every number in this writeup refers to.

## Limitations, honestly

This mirror ships two example managed skills rather than my personal 36, and a compact example standards file rather than my real one, because those are personal or third-party content. The tool currently supports exactly three runtimes; a fourth is specced with placeholders but deliberately not built until I adopt a fourth assistant. The unattended version of the proposal agent remains gated behind two weeks of watcher stability, a control I chose to keep even while shipping the supervised version. The full limitations document in the repo lists every accepted boundary, because knowing what a security tool does not do is part of trusting it.
