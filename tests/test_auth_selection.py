"""Auth backend selection: OAuth-first, API-key fallback, no-op last.

These mock the claude CLI probe and the Anthropic client so they're deterministic
and never touch the network or the real CLI.
"""

import pytest

from komi.adapters.claude_code import llm as llm_mod
from komi.adapters.claude_code.llm_cli import AuthProbe, ClaudeCLILLM, _clean_env


# ── _clean_env (the bug that broke OAuth) ──────────────────────────────────

def test_clean_env_preserves_credential_vars(monkeypatch):
    # The regression: an allowlist stripped these and broke `claude auth status`.
    for k in ("USERNAME", "USERDOMAIN", "ALLUSERSPROFILE", "APPDATA", "PATH", "HOME"):
        monkeypatch.setenv(k, "x")
    env = _clean_env()
    for k in ("USERNAME", "USERDOMAIN", "ALLUSERSPROFILE", "APPDATA", "PATH"):
        assert k in env, f"{k} must be preserved for credential resolution"


def test_clean_env_drops_claude_code_runtime_vars(monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "1")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "abc")
    monkeypatch.setenv("CLAUDE_CODE_ENTRYPOINT", "cli")
    env = _clean_env()
    assert "CLAUDECODE" not in env
    assert "CLAUDE_CODE_SESSION_ID" not in env
    assert "CLAUDE_CODE_ENTRYPOINT" not in env


# ── AuthProbe summaries ────────────────────────────────────────────────────

def test_authprobe_summary():
    assert "max" in AuthProbe(ok=True, reason="logged-in", method="claude.ai",
                              subscription="max").summary()
    assert "not logged in" in AuthProbe(ok=False, reason="not-logged-in").summary().lower()


# ── build_llm ordering ─────────────────────────────────────────────────────

class _FakeCLI:
    def __init__(self, ok):
        self.available = True
        self._ok = ok
    def probe(self, force=False):
        return AuthProbe(ok=self._ok, reason="logged-in" if self._ok else "not-logged-in")


class _FakeAPI:
    def __init__(self, ok):
        self.available = ok


def _patch(monkeypatch, *, cli_ok, api_ok):
    monkeypatch.setattr(llm_mod, "_load_komi_env", lambda: None)
    # patch the lazily-imported ClaudeCLILLM
    import komi.adapters.claude_code.llm_cli as cli_mod
    monkeypatch.setattr(cli_mod, "ClaudeCLILLM", lambda: _FakeCLI(cli_ok))
    monkeypatch.setattr(llm_mod, "AnthropicLLM", lambda: _FakeAPI(api_ok))


def test_oauth_preferred_when_logged_in(monkeypatch):
    _patch(monkeypatch, cli_ok=True, api_ok=True)
    got = llm_mod.build_llm(prefer="oauth")
    assert isinstance(got, _FakeCLI)                       # OAuth wins over API key


def test_falls_back_to_api_when_oauth_not_logged_in(monkeypatch):
    _patch(monkeypatch, cli_ok=False, api_ok=True)
    got = llm_mod.build_llm(prefer="oauth")
    assert isinstance(got, _FakeAPI)                       # OAuth unavailable → API key


def test_nullllm_when_nothing_available(monkeypatch):
    _patch(monkeypatch, cli_ok=False, api_ok=False)
    got = llm_mod.build_llm(prefer="oauth")
    assert type(got).__name__ == "NullLLM"                 # degrade, never crash


def test_prefer_api_reverses_order(monkeypatch):
    _patch(monkeypatch, cli_ok=True, api_ok=True)
    got = llm_mod.build_llm(prefer="api")
    assert isinstance(got, _FakeAPI)                       # API key first when asked


def test_probe_is_cached(monkeypatch):
    calls = {"n": 0}
    cli = ClaudeCLILLM.__new__(ClaudeCLILLM)
    cli.claude_bin = "claude"
    cli._healthy = True
    cli._probe_cache = None

    import komi.adapters.claude_code.llm_cli as m

    class _P:
        returncode = 0
        stdout = '{"loggedIn": true, "authMethod": "claude.ai", "subscriptionType": "max"}'

    def fake_run(*a, **k):
        calls["n"] += 1
        return _P()

    monkeypatch.setattr(m.subprocess, "run", fake_run)
    a = cli.probe()
    b = cli.probe()
    c = cli.probe()
    assert a.ok and b.ok and c.ok
    assert calls["n"] == 1                                 # probed once, then cached
