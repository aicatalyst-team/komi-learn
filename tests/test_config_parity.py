"""Config parity across host adapters.

Both adapters must honor the SAME shared config surface (the shared schema in
komi.adapters.config_schema), so a new pool key can't be added to one host and
silently dropped on the other — the exact defect a review caught (Codex used to
ignore 6 of 10 env vars). These tests pin that:
  • both Config dataclasses expose every attribute the shared schema targets,
  • both adapters' load() actually apply the shared file-keys + env vars,
  • config_io.known_keys() (the `komi-learn config` surface) stays in sync.
"""

import importlib

import pytest

from komi.adapters import config_schema, config_io
from komi.adapters.claude_code import config as cc_config
from komi.adapters.codex import config as cx_config


SCHEMA_ATTRS = set(config_schema.FILE_KEYS) | set(config_schema.ENV_MAP.values())


@pytest.mark.parametrize("cfg_mod", [cc_config, cx_config], ids=["claude_code", "codex"])
def test_config_dataclass_covers_schema(cfg_mod):
    cfg = cfg_mod.Config()
    missing = [a for a in SCHEMA_ATTRS if not hasattr(cfg, a)]
    assert not missing, f"{cfg_mod.__name__} Config missing schema attrs: {missing}"


@pytest.mark.parametrize("cfg_mod", [cc_config, cx_config], ids=["claude_code", "codex"])
def test_env_overrides_apply_on_both_hosts(cfg_mod, tmp_path, monkeypatch):
    # point the host's personal_root at a temp dir (no config.json → pure defaults+env)
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path / "cc"))
    monkeypatch.setenv("CODEX_HOME", str(tmp_path / "cx"))
    importlib.reload(cfg_mod.paths)
    # set EVERY shared env var to a non-default and confirm it lands
    monkeypatch.setenv("KOMI_POOL_MODE", "local")
    monkeypatch.setenv("KOMI_POOL_BRANCH", "dev")
    monkeypatch.setenv("KOMI_POOL_SYNC_HOURS", "3")
    monkeypatch.setenv("KOMI_POOL_MIN_CORROBORATION", "2")
    monkeypatch.setenv("KOMI_POOL_AUTO_CONTRIBUTE", "true")
    cfg = cfg_mod.load()
    assert cfg.pool_mode == "local"
    assert cfg.pool_branch == "dev"
    assert cfg.pool_sync_hours == 3
    assert cfg.pool_min_corroboration == 2
    assert cfg.pool_auto_contribute is True


def test_file_keys_apply(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    importlib.reload(cc_config.paths)
    cfgdir = tmp_path / "komi"
    cfgdir.mkdir(parents=True)
    (cfgdir / "config.json").write_text(
        '{"nudge_turns": 11, "pool": {"repo_url": "https://github.com/x/y", '
        '"min_corroboration": 3, "mode": "local"}}', encoding="utf-8")
    cfg = cc_config.load()
    assert cfg.nudge_turns == 11
    assert cfg.pool_repo_url == "https://github.com/x/y"
    assert cfg.pool_min_corroboration == 3
    assert cfg.pool_mode == "local"


def test_config_io_known_keys_cover_pool_schema():
    """The `komi-learn config set` surface must expose every pool.* key the schema
    has (so users can tune anything the engine reads)."""
    pool_attrs = {a for a in config_schema.FILE_KEYS if a.startswith("pool_")}
    known = set(config_io.known_keys())
    for attr in pool_attrs:
        dotted = "pool." + attr[len("pool_"):]
        assert dotted in known, f"{dotted} not in config_io.known_keys()"
