"""Integrity guard for the Tier 3 eval dataset (evals/tier3/).

The dataset itself is executed by an AI drafting agent; these tests guard the
ground truth: every case is complete, and the adversarial inputs really do
trip the deterministic gates (a known-bad that scans clean is a broken eval).
"""

from pathlib import Path

from agent_config_sync.neutralize import find_vendor_terms
from agent_config_sync.secrets import find_secrets

CASES = Path(__file__).resolve().parents[1] / "evals" / "tier3" / "cases"


def test_every_case_has_input_and_expected():
    dirs = sorted(p for p in CASES.iterdir() if p.is_dir())
    assert len(dirs) == 5
    for d in dirs:
        assert (d / "input.md").exists(), d.name
        assert (d / "expected.md").exists(), d.name
        assert "MUST" in (d / "expected.md").read_text("utf-8"), d.name


def test_vendor_terms_case_is_a_valid_known_bad():
    # should-fail input: if the lint stops catching this, the eval is void
    body = (CASES / "case03-vendor-terms" / "input.md").read_text("utf-8")
    assert find_vendor_terms(body), "case03 input no longer trips the neutral lint"


def test_secret_case_is_a_valid_known_bad():
    body = (CASES / "case04-secret" / "input.md").read_text("utf-8")
    assert find_secrets(body), "case04 input no longer trips the secret scan"


def test_benign_case_is_actually_clean():
    body = (CASES / "case01-benign" / "input.md").read_text("utf-8")
    assert not find_vendor_terms(body) and not find_secrets(body)
