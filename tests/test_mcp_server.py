import json

from agent_config_sync.config import load_config
from agent_config_sync.enroll import enroll_skill
from agent_config_sync.mcp_server import TOOLS, handle_request
from agent_config_sync.project import project
from agent_config_sync.skills import project_skills

NEUTRAL = "---\nname: demo\ndescription: demo skill\n---\n\nDispatch a subagent.\n"


def _cfg(fake_env):
    return load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)


def _clean_state(fake_env):
    (fake_env.repo / "skills" / "demo").mkdir(parents=True, exist_ok=True)
    (fake_env.repo / "skills" / "demo" / "SKILL.md").write_text(NEUTRAL, "utf-8")
    enroll_skill(_cfg(fake_env), "demo", NEUTRAL)
    cfg = _cfg(fake_env)
    project(cfg)
    project_skills(cfg)
    return cfg


def _rpc(method, req_id=1, params=None):
    req = {"jsonrpc": "2.0", "id": req_id, "method": method}
    if params is not None:
        req["params"] = params
    return req


def test_initialize_and_tools_list(fake_env):
    cfg = _clean_state(fake_env)
    resp = handle_request(cfg, _rpc("initialize"))
    assert resp["result"]["serverInfo"]["name"] == "agent-config-sync"
    resp = handle_request(cfg, _rpc("tools/list"))
    assert {t["name"] for t in resp["result"]["tools"]} == {"sense", "check", "status"}


def test_sense_tool_returns_findings_json(fake_env):
    cfg = _clean_state(fake_env)
    fake_env.seed_skill("claude", "extra", "# Extra\nbody\n")
    resp = handle_request(cfg, _rpc("tools/call", params={"name": "sense"}))
    payload = json.loads(resp["result"]["content"][0]["text"])
    assert payload["count"] == 1
    assert payload["findings"][0]["kind"] == "unmanaged-skill"


def test_notifications_get_no_response(fake_env):
    cfg = _clean_state(fake_env)
    assert handle_request(cfg, {"jsonrpc": "2.0", "method": "notifications/initialized"}) is None


def test_unknown_tool_and_method_are_clean_errors(fake_env):
    # should-fail: bad input yields JSON-RPC errors, never exceptions
    cfg = _clean_state(fake_env)
    resp = handle_request(cfg, _rpc("tools/call", params={"name": "project"}))
    assert resp["error"]["code"] == -32602  # mutating command is not a tool here
    resp = handle_request(cfg, _rpc("resources/list"))
    assert resp["error"]["code"] == -32601


def test_no_mutating_surface_exposed(fake_env):
    # should-fail (blocking): the tool list must never grow a mutating verb
    mutating = {"project", "enroll", "promote", "capture", "install-hooks", "prune-backups"}
    assert not mutating & {t["name"] for t in TOOLS}
    import agent_config_sync.mcp_server as m
    import inspect
    src = inspect.getsource(m)
    for verb in ("project_skills", "enroll_skill", "promote_instruction", "atomic_write"):
        assert verb not in src, f"mcp_server must not reference {verb}"
