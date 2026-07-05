import json

from agent_config_sync.audit import AUDIT_FILE, append_audit


def test_append_audit_is_appendonly_jsonl(tmp_path):
    append_audit(tmp_path, {"runtime": "claude", "kind": "create"})
    append_audit(tmp_path, {"runtime": "codex", "kind": "update"})
    lines = (tmp_path / AUDIT_FILE).read_text("utf-8").splitlines()
    assert len(lines) == 2
    assert json.loads(lines[0])["runtime"] == "claude"
    assert json.loads(lines[1])["kind"] == "update"
