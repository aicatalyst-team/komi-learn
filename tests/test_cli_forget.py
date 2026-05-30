"""Phase 7 — `komi-learn forget` (erasure / right to be forgotten).

Driven through cmd_forget with a temp host root; ask_yes_no monkeypatched so the
confirm prompt doesn't block. Covers archive-default, --hard delete, cancel, and
the no-match path.
"""

import argparse
import importlib

import pytest

from komi.engine.store import Store
from komi.engine.model import Learning, LearningType, Category, Scope
from komi import cli, cli_prompt


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    from komi.adapters.claude_code import paths as cc_paths
    importlib.reload(cc_paths)
    return tmp_path


def _args(**kw):
    ns = argparse.Namespace(host="claude-code", hard=False)
    for k, v in kw.items():
        setattr(ns, k, v)
    return ns


def _sem(title, body="b"):
    return Learning(type=LearningType.SEMANTIC.value, category=Category.TOOLING.value,
                    title=title, body=body, scope=Scope.PERSONAL.value).finalize()


def _store():
    from komi.adapters.claude_code import paths as cc_paths
    return Store(cc_paths.personal_root(), index_path=cc_paths.index_path())


def test_forget_archives_by_default(home, monkeypatch):
    s = _store()
    lng = _sem("a preference about tabs")
    s.upsert(lng)
    monkeypatch.setattr(cli_prompt, "ask_yes_no", lambda *a, **k: True)
    assert cli.cmd_forget(_args(query="tabs")) == 0
    states = {l.id: l.lifecycle.state for l in _store().all()}
    assert states.get(lng.id) == "archived"


def test_forget_hard_deletes(home, monkeypatch):
    s = _store()
    lng = _sem("erase this entirely")
    s.upsert(lng)
    monkeypatch.setattr(cli_prompt, "ask_yes_no", lambda *a, **k: True)
    assert cli.cmd_forget(_args(query=lng.id, hard=True)) == 0
    assert lng.id not in {l.id for l in _store().all()}


def test_forget_cancel_leaves_intact(home, monkeypatch):
    s = _store()
    lng = _sem("do not touch me")
    s.upsert(lng)
    monkeypatch.setattr(cli_prompt, "ask_yes_no", lambda *a, **k: False)
    cli.cmd_forget(_args(query="touch"))
    assert {l.lifecycle.state for l in _store().all() if l.id == lng.id} == {"active"}


def test_forget_no_match(home):
    assert cli.cmd_forget(_args(query="zzz-nothing-zzz")) == 0
