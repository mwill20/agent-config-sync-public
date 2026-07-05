def test_package_imports():
    import agent_config_sync

    assert agent_config_sync.__version__ == "0.1.0"


def test_fake_env_has_sources(fake_env):
    assert (fake_env.repo / "_shared" / "core.md").exists()
    assert (fake_env.repo / "config" / "targets.yaml").exists()
    assert len(fake_env.allowed_roots) == 3
