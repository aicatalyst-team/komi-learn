"""Installer: merge-not-clobber, backup, idempotency, uninstall, doctor, env load.

All against a temp CLAUDE_CONFIG_DIR so the real ~/.claude is never touched.
"""

import json

import pytest

from komi.adapters.claude_code import setup, doctor


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    # paths reads the env lazily, so no reload needed; return the dir
    return tmp_path


def _settings(home):
    return json.loads((home / "settings.json").read_text(encoding="utf-8"))


def test_install_creates_hooks_and_config(home):
    rep = setup.install()
    assert rep.ok
    s = _settings(home)
    assert "SessionStart" in s["hooks"]
    cmds = [h["command"] for e in s["hooks"]["SessionStart"] for h in e["hooks"]]
    assert any("komi.adapters.claude_code.hook_recall" in c for c in cmds)
    # config written
    assert (home / "komi" / "config.json").exists()


def test_install_uses_absolute_python_path(home):
    setup.install()
    s = _settings(home)
    cmd = next(h["command"] for e in s["hooks"]["SessionStart"] for h in e["hooks"]
               if "komi.adapters" in h["command"])
    # absolute path, not bare "python" — the robustness guarantee
    assert cmd.split()[0] not in ("python", "python3", '"python"')


def test_install_merges_not_clobbers(home):
    (home / "settings.json").write_text(json.dumps({
        "alwaysThinkingEnabled": True,
        "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo MINE"}]}]},
    }), encoding="utf-8")
    setup.install()
    s = _settings(home)
    assert s["alwaysThinkingEnabled"] is True                # preserved
    cmds = [h["command"] for e in s["hooks"]["SessionStart"] for h in e["hooks"]]
    assert any("echo MINE" in c for c in cmds)               # user's hook kept
    assert any("komi.adapters" in c for c in cmds)           # ours added
    assert (home / "settings.json.komi-bak").exists()        # backup made


def test_install_is_idempotent(home):
    setup.install()
    setup.install()
    setup.install()
    s = _settings(home)
    cmds = [h["command"] for e in s["hooks"]["SessionStart"] for h in e["hooks"]]
    assert sum(1 for c in cmds if "komi.adapters" in c) == 1  # never duplicated


def test_install_self_heals_stale_hook_command(home):
    # Simulate an old install that used bare 'python' (or a moved repo path).
    (home / "settings.json").write_text(json.dumps({
        "hooks": {"SessionStart": [{"hooks": [
            {"type": "command", "command": "python -m komi.adapters.claude_code.hook_recall"}
        ]}]},
    }), encoding="utf-8")
    setup.install()
    s = _settings(home)
    cmds = [h["command"] for e in s["hooks"]["SessionStart"] for h in e["hooks"]
            if "komi.adapters" in h["command"]]
    assert len(cmds) == 1                                    # refreshed, not duplicated
    assert cmds[0].split()[0] not in ("python", "python3")   # upgraded to absolute path


def test_install_stores_api_key(home):
    setup.install(api_key="sk-test-key-1234567890")
    env = (home / "komi" / ".env").read_text(encoding="utf-8")
    assert "ANTHROPIC_API_KEY=sk-test-key-1234567890" in env


def test_install_without_model_still_succeeds(home, monkeypatch):
    # No API key, no claude CLI — recall must still install fine.
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    rep = setup.install()
    assert rep.ok                                            # core succeeds
    model_step = next(s for s in rep.steps if s.name == "model")
    assert model_step.ok                                    # best-effort, not a failure


def test_uninstall_removes_hooks_keeps_data(home):
    setup.install(api_key="sk-x-1234567890123456")
    setup.uninstall(keep_data=True)
    s = _settings(home)
    cmds = [h["command"] for ev in s.get("hooks", {}).values()
            for e in ev for h in e.get("hooks", [])]
    assert not any("komi.adapters" in c for c in cmds)      # hooks gone
    assert (home / "komi" / "config.json").exists()         # data kept


def test_uninstall_preserves_other_hooks(home):
    (home / "settings.json").write_text(json.dumps({
        "hooks": {"SessionStart": [{"hooks": [{"type": "command", "command": "echo MINE"}]}]},
    }), encoding="utf-8")
    setup.install()
    setup.uninstall()
    s = _settings(home)
    cmds = [h["command"] for e in s["hooks"]["SessionStart"] for h in e["hooks"]]
    assert any("echo MINE" in c for c in cmds)              # user's hook survives uninstall


def test_doctor_runs_clean_after_install(home):
    setup.install(api_key="sk-x-1234567890123456")
    checks = doctor.run_doctor()
    by = {c.name: c for c in checks}
    assert by["install"].status == "pass"
    assert by["hooks"].status == "pass"
    assert by["distillation"].status == "pass"              # has key
    # no hard failures
    assert all(c.status != "fail" for c in checks)


def test_doctor_flags_missing_hooks(home):
    # config dir exists but no install run
    (home / "settings.json").write_text("{}", encoding="utf-8")
    checks = doctor.run_doctor()
    hooks = next(c for c in checks if c.name == "hooks")
    assert hooks.status == "fail"
    assert "install" in hooks.fix.lower()


def test_env_loader_picks_up_stored_key(home, monkeypatch):
    setup.install(api_key="sk-stored-9876543210")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from komi.adapters.claude_code import llm
    llm._load_komi_env()
    import os
    assert os.environ.get("ANTHROPIC_API_KEY") == "sk-stored-9876543210"
