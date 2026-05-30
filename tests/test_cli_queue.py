"""Phase 7 — `komi-learn queue` (review-queue inspection: list / reject).

list + reject are offline (no pool needed). approve→publish to a real pool is not
exercised here (covered by pool tests); we test the human-gate inspection surface.
"""

import argparse
import importlib
import json

import pytest

from komi.engine.model import Learning, LearningType, Category, Scope
from komi import cli


@pytest.fixture
def home(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(tmp_path))
    from komi.adapters.claude_code import paths as cc_paths
    importlib.reload(cc_paths)
    return tmp_path


def _args(**kw):
    ns = argparse.Namespace(host="claude-code")
    for k, v in kw.items():
        setattr(ns, k, v)
    return ns


def _enqueue(title):
    """Write a pending-review item the way the distiller does."""
    from komi.adapters.claude_code import paths as cc_paths
    g = Learning(type=LearningType.PROCEDURAL.value, category=Category.TOOLING.value,
                 title=title, body="do X then Y", trigger="t", tags=["x"],
                 scope=Scope.GLOBAL.value).finalize()
    d = cc_paths.queue_dir()
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{g.id.replace(':', '_')}.json").write_text(
        json.dumps({"status": "pending-review", "learning": g.to_dict()}),
        encoding="utf-8")
    return g


def test_queue_list_empty(home):
    assert cli.cmd_queue(_args(queue_action="list")) == 0


def test_queue_list_shows_pending(home, capsys):
    _enqueue("a general technique")
    cli.cmd_queue(_args(queue_action="list"))
    assert "a general technique" in capsys.readouterr().out


def test_queue_reject_removes_from_pending(home):
    from komi.pool.queue import list_queue
    from komi.adapters.claude_code import paths as cc_paths
    _enqueue("reject me")
    assert cli.cmd_queue(_args(queue_action="reject", index=0)) == 0
    # no longer pending (status flipped to rejected)
    assert list_queue(cc_paths.queue_dir(), status="pending-review") == []


def test_queue_reject_bad_index(home):
    assert cli.cmd_queue(_args(queue_action="reject", index=99)) == 1


def test_queue_default_action_is_list(home):
    # no queue_action attr at all → defaults to list, empty queue → 0
    ns = argparse.Namespace(host="claude-code")
    assert cli.cmd_queue(ns) == 0
