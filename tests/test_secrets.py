from agent_config_sync.secrets import SecretFoundError, find_secrets


def test_clean_text_has_no_secrets():
    assert find_secrets("# Just docs\nNo credentials here.\n") == []


def test_detects_anthropic_key():
    hits = find_secrets("token: sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAAAA")
    assert hits


def test_detects_openai_project_key():
    assert find_secrets("sk-proj-" + "A1" * 20)


def test_detects_generic_openai_key():
    assert find_secrets("sk-" + "A1" * 20)


def test_detects_aws_access_key():
    assert find_secrets("AKIAIOSFODNN7EXAMPLE")


def test_detects_generic_assignment():
    assert find_secrets('api_key = "supersecretvalue123"')


def test_secret_found_error_carries_context():
    err = SecretFoundError("gemini", ["sk-ant-xxx"])
    assert err.runtime == "gemini"
    assert err.matches == ["sk-ant-xxx"]


def test_detects_suffixed_key_names():
    assert find_secrets('signing_key = "supersecretvalue123"')
    assert find_secrets('private_key: "anothersecretvalue"')


def test_detects_google_api_key():
    assert find_secrets("AIza" + "B" * 35)


def test_detects_github_token():
    assert find_secrets("ghp_" + "a" * 36)


# --- Critique finding #2: lint was near-useless for unquoted markdown prose ---

def test_detects_unquoted_assignment():
    # No quotes — the format these markdown instruction files actually use.
    assert find_secrets("password = hunter2value123")
    assert find_secrets("api_key: AKIAabc123def456ghi789")


def test_detects_slack_bot_token():
    # Deliberately not a realistic token shape (no numeric workspace/bot
    # segments) so this fixture doesn't itself trip GitHub push protection.
    assert find_secrets("xoxb-FAKE-TEST-TOKEN-NOT-REAL-000")


def test_detects_github_fine_grained_pat():
    assert find_secrets("github_pat_" + "A1b2" * 6)


def test_detects_private_key_block_header():
    assert find_secrets("-----BEGIN OPENSSH PRIVATE KEY-----\nbody")


def test_detects_jwt_like_token():
    token = "eyJ" + "a" * 12 + "." + "b" * 12 + "." + "c" * 12
    assert find_secrets(token)


def test_detects_stripe_live_key():
    assert find_secrets("sk_live_" + "a1B2" * 6)


def test_prose_with_no_digit_value_not_flagged():
    # "token: documentation" is prose, not a credential — must not false-positive.
    assert find_secrets("See the token: documentation for details.") == []
    assert find_secrets("Never hardcode secrets; use env vars.") == []
