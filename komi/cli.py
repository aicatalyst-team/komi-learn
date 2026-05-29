"""komi-learn — the user-facing command-line interface.

The command is ``komi-learn`` (a Kurikomi product). One command to set everything
up; a doctor to diagnose; status/sync/uninstall for the rest. Designed so a new
user runs exactly one thing:

    komi-learn install                 # OR: komi-learn install --api-key sk-... \\
                                       #              --pool https://github.com/kurikomi-labs/komi-pool

and recall starts working immediately, with distillation enabled if a model
credential is available.
"""

from __future__ import annotations

import argparse
import sys

PRODUCT = "komi-learn"

# UTF-8 stdout so status glyphs render on Windows consoles too.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

_TICK = {"pass": "✓", "warn": "!", "fail": "✗", True: "✓", False: "✗"}


def _p(line: str = "") -> None:
    print(line)


# ── commands ───────────────────────────────────────────────────────────────

def cmd_install(args) -> int:
    from komi.adapters.claude_code import setup
    _p(f"{PRODUCT}: installing for Claude Code…\n")
    rep = setup.install(pool_repo_url=args.pool, api_key=args.api_key,
                        nudge_turns=args.nudge_turns)
    for s in rep.steps:
        _p(f"  {_TICK[s.ok]} {s.name:12} {s.detail}")
        if not s.ok and s.fix:
            _p(f"      → {s.fix}")
        elif s.fix and s.name in ("model",):
            _p(f"      note: {s.fix}")
    _p()
    if rep.ok:
        _p(f"{PRODUCT} is installed. Recall is active in your next Claude Code session — no commands needed.")
        if not args.pool:
            _p("Tip: join the global pool with  komi-learn install --pool <repo-url>")
        _p("Check anytime with:  komi-learn doctor")
        return 0
    _p(f"{PRODUCT}: install incomplete — see the ✗ items above.")
    return 1


def cmd_doctor(args) -> int:
    from komi.adapters.claude_code.doctor import run_doctor
    _p(f"{PRODUCT} doctor:\n")
    checks = run_doctor()
    worst_fail = False
    for c in checks:
        _p(f"  {_TICK[c.status]} {c.name:13} {c.detail}")
        if c.status != "pass" and c.fix:
            _p(f"      → {c.fix}")
        if c.status == "fail":
            worst_fail = True
    _p()
    if worst_fail:
        _p(f"{PRODUCT}: there are issues above that stop recall from working.")
        return 1
    _p(f"{PRODUCT}: healthy. (Warnings are optional features, not failures.)")
    return 0


def cmd_status(args) -> int:
    from komi.adapters.claude_code import config as cfg_mod, paths
    from komi.engine.store import Store
    cfg = cfg_mod.load()
    _p(f"{PRODUCT} status")
    _p(f"  home:        {paths.personal_root()}")
    _p(f"  pool:        {cfg.pool_repo_url or '(not configured)'}")
    _p(f"  nudge_turns: {cfg.nudge_turns}   sync_hours: {cfg.pool_sync_hours}")
    try:
        s = Store(paths.personal_root(), index_path=paths.index_path())
        learns = s.all()
        by_scope = {}
        for l in learns:
            by_scope[l.scope] = by_scope.get(l.scope, 0) + 1
        s.close()
        _p(f"  learnings:   {len(learns)}  ({', '.join(f'{k}:{v}' for k,v in by_scope.items()) or 'none yet'})")
    except Exception as e:
        _p(f"  learnings:   (unavailable: {e})")
    return 0


def cmd_sync(args) -> int:
    from komi.adapters.claude_code import config as cfg_mod
    from komi.pool.github_backend import GitHubPool, PoolConfig
    cfg = cfg_mod.load()
    if not cfg.pool_enabled:
        _p(f"{PRODUCT}: no pool configured. Set one with: komi-learn install --pool <repo-url>")
        return 1
    pool = GitHubPool(PoolConfig(repo_url=cfg.pool_repo_url, cache_dir=cfg.pool_cache_dir,
                                 branch=cfg.pool_branch, require_signature=cfg.pool_require_signature))
    r = pool.sync()
    if r.ok:
        n = len(pool.pull())
        _p(f"{PRODUCT}: synced. {n} learning(s) available from the pool.")
        return 0
    _p(f"{PRODUCT}: sync failed — {r.detail}")
    return 1


def cmd_uninstall(args) -> int:
    from komi.adapters.claude_code import setup
    rep = setup.uninstall(keep_data=not args.purge)
    for s in rep.steps:
        _p(f"  {_TICK[s.ok]} {s.name:8} {s.detail}")
    _p(f"\n{PRODUCT}: uninstalled hooks." +
       ("" if args.purge else " Your learnings were kept (use --purge to remove)."))
    return 0


# ── parser ───────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog=PRODUCT,
        description="komi-learn — a continuous, zero-friction learning layer for AI agents (by Kurikomi).",
    )
    sub = p.add_subparsers(dest="command")

    pi = sub.add_parser("install", help="set up komi-learn for Claude Code (one command)")
    pi.add_argument("--pool", metavar="URL", default=None,
                    help="global pool repo URL (e.g. https://github.com/kurikomi-labs/komi-pool)")
    pi.add_argument("--api-key", metavar="KEY", default=None,
                    help="Anthropic API key for distillation (else uses env / claude CLI)")
    pi.add_argument("--nudge-turns", type=int, default=8,
                    help="distill every N turns (default 8)")
    pi.set_defaults(func=cmd_install)

    pd = sub.add_parser("doctor", help="diagnose the install and suggest fixes")
    pd.set_defaults(func=cmd_doctor)

    ps = sub.add_parser("status", help="show config + learning counts")
    ps.set_defaults(func=cmd_status)

    py = sub.add_parser("sync", help="sync the global pool now")
    py.set_defaults(func=cmd_sync)

    pu = sub.add_parser("uninstall", help="remove komi-learn hooks (keeps data)")
    pu.add_argument("--purge", action="store_true", help="also delete ~/.claude/komi")
    pu.set_defaults(func=cmd_uninstall)

    return p


def main(argv=None) -> int:
    argv = sys.argv[1:] if argv is None else argv
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "func", None):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
