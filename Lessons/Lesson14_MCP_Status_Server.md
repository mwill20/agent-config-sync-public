# 🎓 Lesson 14: The Front Desk Window — A Read-Only MCP Server

## 🛡️ Welcome Back, Security Analyst!

How do you let every tool in the building ask "are we in sync?" without handing
any of them a key? 🔍 Today we explore the **MCP status server**
(`src/agent_config_sync/mcp_server.py`), the "front desk window" where any
MCP-capable AI or tool can ask questions and receive answers, while the door
beside the window stays locked.

---

## 🎯 Learning Objectives

By the end of this lesson you will be able to:

- Explain what MCP (Model Context Protocol) is and when a server is worth exposing
- Trace one JSON-RPC exchange from stdin line to stdout response
- Defend a read-only-by-construction tool surface in a security review
- Show why a hand-rolled protocol subset beat adding an SDK dependency here
- Prove the no-mutating-surface property with the project's own should-fail test

**Time estimate:** 25 minutes | **Prerequisites:** Lesson 12 (operator loop) helps

---

## 🧠 What This Component Does — Plain English

MCP is a standard way for AI tools to discover and call capabilities another
program offers, like a universal power outlet for tool access. This server
plugs agent-config-sync into that outlet, but only the *asking* half: any
connected AI can call `sense`, `check`, or `status` and get the same JSON the
CLI produces. There is no plug for writing. The mutating commands (project,
enroll, promote) simply do not exist on this surface.

It speaks newline-delimited JSON-RPC 2.0 over stdin/stdout, the simplest MCP
transport. Start it with `agent-config-sync mcp-serve`, point an MCP client at
that command, and the client sees three read-only tools.

**Real-world analogy:** the records window at a courthouse. Anyone can request
a copy of a filing through the glass; nobody at the window can accept edits to
the originals, because the window room has no filing access at all.

---

## 🔵🟡🔴 Career Lens — Three Perspectives on This Component

### 🔵 Analyst Lens — What a SOC Analyst Sees Here

This is a **read-only API integration**, the same shape as wiring VirusTotal
lookups into a SOAR playbook: external callers get enrichment answers, never
write access to your case data. The tool descriptions even carry the standing
instruction ("ask the operator before running any resolution command"), the
way a TI feed labels confidence so downstream automation behaves.

**SOC parallel:** a read-only Swimlane enrichment endpoint: queryable by every
playbook, capable of changing nothing.

### 🟡 Engineer Lens — What a Cybersecurity Engineer Builds Here

Two decisions to own. First, **subset over SDK**: the server hand-implements
the four JSON-RPC methods it needs (initialize, ping, tools/list, tools/call)
instead of importing an MCP SDK, because this project pins its supply chain
and the needed subset is about a hundred lines. The cost is honest and
documented in the module docstring: the subset targets protocol version
2024-11-05 and must be re-verified against the spec before extending. Second,
**errors as data**: a failing tool call returns `isError: true` content and an
unknown method returns a JSON-RPC error object; the serve loop cannot crash on
malformed input (parse errors get error responses too).

**Engineering decision to own:** capability minimization at the protocol
layer. The safest write endpoint is the one that was never implemented.

### 🔴 AI Security Engineer Lens — What an AI/ML Security Engineer Watches For

An MCP server is a **tool grant to language models**. Whatever you expose, an
LLM will eventually be prompt-injected into calling, so the design assumes a
hostile caller: every tool is read-only, tool output is fixed deterministic
phrasing built from validated names (the same guarantee as the session hook,
Lesson 13), and the should-fail test asserts no mutating function is even
importable from the module. Least privilege is enforced where the attacker
cannot negotiate: in what code exists.

**AI security surface:** tool-grant scope for LLM callers. Control: read-only
by construction plus a regression test that fails if anyone ever adds a
mutating verb to the tool list.

---

## 🗺️ Where This Fits in the System

```
 MCP client (any AI/tool) ──stdin──▶ mcp-serve ──▶ sense.scan / check / status
                          ◀─stdout──    │                (read-only modules)
                                        ✗ no path to project/enroll/promote
```

If this server is off, nothing degrades except external queryability; the CLI,
hooks, and watcher are unaffected.

---

## 🔑 Key Concepts

### MCP (Model Context Protocol)
A protocol letting AI applications discover and call tools another process
offers, over transports like stdio. Client asks `tools/list`, then invokes
with `tools/call`.

### Read-only by construction
The security property is structural: the module never imports a mutating
function, so no bug, injection, or future patch to *this file's callers* can
mutate state through it. Enforced by `test_no_mutating_surface_exposed`.

### JSON-RPC notification
A request without an `id` expects no response (`notifications/initialized`).
Answering one is a protocol violation; the handler returns `None` for them.

---

## 📝 Code Walkthrough

### The dispatch core

```python
# src/agent_config_sync/mcp_server.py — handle_request (excerpt)
    if method == "tools/call":
        params = req.get("params") or {}
        name = params.get("name", "")
        if name not in {t["name"] for t in TOOLS}:
            return err(-32602, f"unknown tool '{name}'")
        try:
            text = _call_tool(config, name)
        except Exception as exc:  # noqa: BLE001 - report, never crash the server
            return ok({"content": [{"type": "text", "text": f"error: {exc}"}], "isError": True})
        return ok({"content": [{"type": "text", "text": text}]})
    return err(-32601, f"method '{method}' not supported (read-only status server)")
```

| Lines | What it does | Why it was designed this way |
|-------|-------------|------------------------------|
| allowlist check | Tool name must be in the fixed `TOOLS` list | Caller-supplied names never reach dynamic dispatch |
| broad except | Tool failure becomes `isError` content | A hostile or broken call must not kill the server loop |
| final `err` | Everything unimplemented is an explicit refusal | The unsupported surface is named, not silently ignored |

> ⚠️ **Common pitfall:** extending the server by importing a mutating helper
> "just for one admin tool." That single import deletes the structural
> guarantee; the should-fail test exists to make that change loud.

---

## 🧪 Hands-On Exercises

### 🔬 Exercise 1: Handshake and a tool call

```powershell
'{"jsonrpc":"2.0","id":1,"method":"initialize"}
{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"check"}}' | agent-config-sync mcp-serve
```

```bash
printf '{"jsonrpc":"2.0","id":1,"method":"initialize"}\n{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"check"}}\n' | agent-config-sync mcp-serve
```

📊 **Expected output:** two JSON lines: `serverInfo` naming `agent-config-sync`,
then a `content` block whose text is `{"stale": []}` on a clean tree.

✅ **You succeeded if:** both responses arrive and the process exits cleanly at
end of input.

### 🔬 Exercise 2: Intentional Failure — ask for a mutating verb

```bash
printf '{"jsonrpc":"2.0","id":1,"method":"tools/call","params":{"name":"project"}}\n' | agent-config-sync mcp-serve
```

📊 **Expected output:** `{"jsonrpc": "2.0", "id": 1, "error": {"code": -32602, "message": "unknown tool 'project'"}}`

✅ **You succeeded if:** the mutating verb is refused as *unknown*, proof it
does not exist on this surface rather than being merely forbidden.

### 🔬 Exercise 3: Garbage input

```bash
printf 'not json at all\n' | agent-config-sync mcp-serve
```

📊 **Expected output:** a `-32700` parse error response; no traceback.

✅ **You succeeded if:** the server answers with a protocol error and keeps
its loop intact.

---

## 📚 Interview Preparation

### 🟡 Cybersecurity Engineering Interview

**Q:** You need to expose internal system state to third-party tooling. Walk
me through how you scope that endpoint.

**A:** Start from what must never happen and make it structurally impossible:
here, external mutation. The module exposing the endpoint imports only
read-only functions, so there is no code path to abuse, and a regression test
fails the build if a mutating import ever appears. Then minimize the protocol:
implement only the methods clients need, refuse the rest explicitly, and turn
every failure into a well-formed error so malformed input cannot crash the
loop. Finally, keep output deterministic and built from validated identifiers
so the endpoint cannot become a data-exfiltration or injection channel.

*Why this answer works:* it scopes by construction and verification, not by
policy statements.

### 🔴 AI Security Engineering Interview

**Q:** What changes about API design when the caller is an LLM agent rather
than a human developer?

**A:** Assume the caller can be talked into anything, because prompt injection
means it eventually will be. So the grant itself must be safe under a fully
adversarial caller: read-only tools, no free-text parameters where they are
not needed (these tools take none), fixed-phrasing outputs so the response
cannot smuggle instructions into the next model's context, and instructions in
the tool description telling the agent to route consequential actions to the
operator. You design the tool surface the way you would design permissions
for untrusted code, not the way you document an SDK for a colleague.

*Why this answer works:* it treats the LLM caller as an untrusted principal
and designs the grant accordingly.

---

## ✅ Key Takeaways

- MCP makes the sync state queryable by any AI tool; the write path stays CLI-and-operator only
- Read-only by construction beats read-only by policy, and a should-fail test keeps it true
- A documented protocol subset with zero dependencies fit this project better than an SDK
- Hostile-caller assumptions (errors as data, no crash on garbage) are baseline for LLM-facing surfaces

---

## 📋 Quick Reference Card

| Item | Value |
|------|-------|
| File | `src/agent_config_sync/mcp_server.py` |
| Entry point | `serve(config)` / CLI `mcp-serve` |
| Input | newline-delimited JSON-RPC 2.0 on stdin |
| Output | JSON-RPC responses on stdout |
| Tools | `sense`, `check`, `status` (all read-only) |
| Error behavior | parse error → -32700; unknown tool → -32602; tool failure → isError content |
| Dependencies | stdlib + read-only project modules only |
| Test file | `tests/test_mcp_server.py` |

---

## 📌 Implemented vs. Recommended

### What This Project Implements ✅
- Tool serving subset of MCP 2024-11-05 over stdio (`mcp_server.py`)
- Structural read-only guarantee with regression test (`test_no_mutating_surface_exposed`)

### General Best Practices — Recommended but Not Implemented Here
- Full MCP capability negotiation (resources, prompts, notifications) — `Recommended (not implemented here)`
- Per-client authentication for network transports — `Recommended (not implemented here; stdio inherits the local user boundary)`

---

## ⚖️ Decisions & Trade-offs

### Decisions Touched
| Decision | Statement | Why It Matters Here |
|----------|-----------|---------------------|
| Subset over SDK | Hand-rolled four-method JSON-RPC, no new dependency | Supply-chain pinning policy; the subset is ~100 auditable lines |
| Read-only tool grant | sense/check/status only | LLM callers are assumed injectable; mutation stays with the operator CLI |

### What We Explicitly Rejected
- **Official MCP SDK dependency:** capable but unpinned surface area for a
  three-tool read-only server; rejected under the exact-pin supply-chain rule.
- **A `project` tool over MCP:** would hand remote mutation to any connected
  model; contradicts the operator-holds-the-pen principle.

### Trade-off Log
| Choice Made | What We Gained | What We Gave Up |
|-------------|----------------|-----------------|
| Protocol subset | Zero dependencies, full auditability | Manual tracking of MCP spec evolution |
| stdio transport only | Inherits local-user trust boundary | No remote/network clients |

### Future Gate Conditions
- MCP spec revision changing the initialize handshake → re-verify against the
  published spec before any client onboarding
- A need for network transport → requires authentication design first

---

## 🚀 Curriculum Complete

Lessons 00 through 14 now cover the full system: projector, gates, drift
guard, skills, capture/promote, hooks, hardening, operator loop, ambient
watcher, and the MCP window.

**Optional deeper dive:** the MCP specification at modelcontextprotocol.io;
compare its full lifecycle section with this server's four-method subset.

**Modification challenge (<30 min):** add a read-only `overlap` tool that
takes a `name` and `runtime` parameter, reusing `overlap.compare`. Note what
NEW risk parameters introduce (caller-controlled strings) and which existing
validator you must call first.

*Remember: the safest endpoint is the one where the dangerous verb was never implemented.* 🛡️
