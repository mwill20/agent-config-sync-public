from agent_config_sync.neutralize import find_vendor_terms


def test_flags_claude_skill_tool():
    assert "Skill tool" in find_vendor_terms("Invoke the Skill tool to run it.")


def test_flags_codex_apply_patch():
    assert "apply_patch" in find_vendor_terms("Edit files with apply_patch.")


def test_flags_gemini_activate_skill():
    assert "activate_skill" in find_vendor_terms("Load it with activate_skill.")


def test_flags_slash_command():
    terms = find_vendor_terms("Run /critique before merging.")
    assert any(t.startswith("/") for t in terms)


def test_flags_other_named_tools():
    assert "Bash tool" in find_vendor_terms("Run it with the Bash tool.")
    assert "Edit tool" in find_vendor_terms("Use the Edit tool to change files.")
    assert "Read tool" in find_vendor_terms("Open it with the Read tool.")


def test_flags_mcp_tool_name():
    terms = find_vendor_terms("Call mcp__github__create_pull_request to open a PR.")
    assert any(t.startswith("mcp__") for t in terms)


def test_flags_bare_tool_identifiers():
    assert "TodoWrite" in find_vendor_terms("Track work with TodoWrite.")
    assert "subagent_type" in find_vendor_terms("Set subagent_type to Explore.")


def test_flags_runtime_callable_identifiers():
    text = "Use shell_command, request_user_input, web.run, web__run, and functions.shell_command."
    terms = find_vendor_terms(text)
    assert "shell_command" in terms
    assert "request_user_input" in terms
    assert "web.run" in terms
    assert "web__run" in terms
    assert "functions.shell_command" in terms


def test_flags_tool_names_case_insensitively():
    assert "bash tool" in find_vendor_terms("Use the bash tool here.")


def test_neutral_body_is_clean():
    body = "Dispatch a subagent to read the file, then report findings."
    assert find_vendor_terms(body) == []


def test_generic_prose_tool_not_flagged():
    # Lowercase 'tool' in ordinary prose must not trip the lint (no false abort).
    assert find_vendor_terms("Pick the right tool for the job.") == []
    assert find_vendor_terms("This tool keeps configs in sync.") == []


import pytest

from agent_config_sync.config import load_config
from agent_config_sync.neutralize import (
    ReconciliationError,
    read_skill_variants,
    reconcile_skill,
)


def _cfg(fake_env):
    return load_config(fake_env.repo, allowed_roots=fake_env.allowed_roots)


def test_read_variants_finds_seeded_skills(fake_env):
    fake_env.seed_skill("claude", "demo", "# Demo\nbody\n")
    fake_env.seed_skill("gemini", "demo", "# Demo\nbody\n")
    variants = read_skill_variants(_cfg(fake_env), "demo")
    assert set(variants) == {"claude", "gemini"}


def test_reconcile_identical_returns_body():
    assert reconcile_skill({"claude": "x\n", "gemini": "x\n"}) == "x\n"


def test_reconcile_divergent_raises():
    with pytest.raises(ReconciliationError) as exc:
        reconcile_skill({"claude": "a\n", "codex": "b\n"})
    assert set(exc.value.runtimes) == {"claude", "codex"}


def test_reconcile_divergent_with_canonical_picks_it():
    body = reconcile_skill({"claude": "a\n", "codex": "b\n"}, canonical="codex")
    assert body == "b\n"


def test_wrapped_slash_command_detected_for_known_skill_names():
    # Codex audit finding: `/critique` in backticks bypassed the whitespace rule
    assert "/critique" in find_vendor_terms(
        "Run `/critique` before merging.", skill_names=("critique",)
    )
    assert "/critique" in find_vendor_terms(
        'See "(/critique)" for review.', skill_names=("critique",)
    )


def test_quoted_url_path_not_flagged_as_skill_command():
    # regression: neutralized route examples must stay clean
    assert find_vendor_terms('`GET "/cases/{case_id}"`', skill_names=("critique",)) == []


def test_directory_path_containing_skill_name_not_flagged():
    text = "See docs/threat-model notes and https://x.example/threat-model page."
    assert find_vendor_terms(text, skill_names=("threat-model",)) == []


def test_gemini_tool_names_flagged():
    # gap found 2026-07-04: a Gemini-authored skill scanned clean while
    # naming Gemini-specific tools
    hits = find_vendor_terms("Use your grep_search and list_dir tools, then run_shell_command.")
    assert "grep_search" in hits and "list_dir" in hits and "run_shell_command" in hits
