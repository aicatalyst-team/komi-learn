"""The interactive install wizard + `komi-learn config` (post-install tinkering).

All tests run NON-interactively (assume_yes / config set), so no stdin blocking.
Covers: wizard defaults (pool ON, semantic ON, contribution human-gated), prompt
helpers fall back to defaults off-TTY, config get/set/coercion, and the
semantic-disable flag forcing keyword recall even with the model present.
"""

import json

import pytest

from komi.adapters import config_io
from komi.adapters.claude_code import paths as cc_paths
from komi import cli_prompt, wizard


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    import importlib
    importlib.reload(cc_paths)
    return tmp_path


# ── wizard defaults ──────────────────────────────────────────────────────────

def test_wizard_yes_applies_recommended_defaults(home):
    choices = wizard.run_wizard(host="claude-code", pool_url=None, api_key=None,
                                nudge_turns=8, assume_yes=True)
    cfg = json.loads((home / "komi" / "config.json").read_text(encoding="utf-8"))
    assert cfg["pool"]["repo_url"] == wizard.DEFAULT_POOL_URL    # pool ON by default
    assert cfg["recall"]["semantic"] is True                    # semantic ON
    assert cfg["pool"]["auto_contribute"] is False              # contributing stays human-gated
    assert choices["pool_url"] == wizard.DEFAULT_POOL_URL


def test_wizard_respects_explicit_pool_url(home):
    wizard.run_wizard(host="claude-code", pool_url="https://github.com/me/mine",
                      api_key=None, nudge_turns=8, assume_yes=True)
    cfg = json.loads((home / "komi" / "config.json").read_text(encoding="utf-8"))
    assert cfg["pool"]["repo_url"] == "https://github.com/me/mine"


# ── prompt helpers fall back safely (no TTY) ─────────────────────────────────

def test_prompts_use_default_when_assume_yes(monkeypatch):
    cli_prompt.ASSUME_YES = True
    try:
        assert cli_prompt.ask_yes_no("x?", default=True) is True
        assert cli_prompt.ask_yes_no("x?", default=False) is False
        assert cli_prompt.ask_choice("pick", [("a", "A"), ("b", "B")], default=1) == "b"
        assert cli_prompt.ask_text("name", default="d") == "d"
    finally:
        cli_prompt.ASSUME_YES = False


# ── config_io get/set/coercion ───────────────────────────────────────────────

def test_config_set_dotted_and_coerce():
    d = {}
    config_io.set_key(d, "pool.repo_url", "https://x")
    config_io.set_key(d, "recall.semantic", "false")   # string → bool
    config_io.set_key(d, "nudge_turns", "12")          # string → int
    assert d["pool"]["repo_url"] == "https://x"
    assert d["recall"]["semantic"] is False
    assert d["nudge_turns"] == 12
    assert config_io.get_key(d, "recall.semantic") is False


def test_config_save_load_roundtrip(home):
    d = {"nudge_turns": 5, "pool": {"repo_url": "https://x"}}
    assert config_io.save_raw(cc_paths, d) is True
    assert config_io.load_raw(cc_paths) == d


# ── semantic-disable flag forces keyword recall ──────────────────────────────

def test_semantic_pref_flag(monkeypatch):
    from komi.engine import embed
    monkeypatch.setenv("KOMI_SEMANTIC", "0")
    embed._reset_cache_for_tests()
    assert embed.semantic_enabled() is False
    assert embed.get_embedder() is None                # disabled → keyword fallback
    monkeypatch.setenv("KOMI_SEMANTIC", "1")
    embed._reset_cache_for_tests()
    assert embed.semantic_enabled() is True
    embed._reset_cache_for_tests()


def test_hooklib_exports_semantic_pref(home, monkeypatch):
    # writing recall.semantic=false to config → hooklib sets KOMI_SEMANTIC=0
    config_io.save_raw(cc_paths, {"recall": {"semantic": False}})
    monkeypatch.delenv("KOMI_SEMANTIC", raising=False)
    from komi.adapters import hooklib
    hooklib._apply_semantic_pref(cc_paths)
    import os
    assert os.environ.get("KOMI_SEMANTIC") == "0"
