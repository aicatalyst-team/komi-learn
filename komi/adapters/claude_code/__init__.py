"""Claude Code adapter for komi-learn.

Zero friction by construction:
  • SessionStart hook → inject recalled learnings as additionalContext
  • Stop / SubagentStop hook → spawn the distiller detached (never blocks the turn)

Both are thin: they read the hook JSON from stdin, call the engine, and either
print a hook response (recall) or fork-and-exit (distill). No slash commands.

The host-specific plumbing lives in the hook modules; ``ClaudeCodeAdapter`` below
implements the host-agnostic :class:`komi.adapters.base.Adapter` contract so the
"two-method interface" is real and a second host has a known surface to copy.
"""

from __future__ import annotations

from ..base import Adapter, RecallContext


class ClaudeCodeAdapter(Adapter):
    """Binds the engine to Claude Code. The hooks delegate their core logic here;
    the entry-point shells (stdin parsing, detached spawn) stay in the hook modules."""

    name = "claude-code"

    def recall(self, context: RecallContext) -> str:
        from ...engine.recall import recall as _recall, RecallConfig
        from .hook_recall import _merged_store
        store = _merged_store(context.cwd)
        return _recall(store, cwd=context.cwd, recent_files=context.recent_files,
                       prompt_hint=context.prompt_hint, config=RecallConfig())

    def on_session_end(self, turns: list[dict]):
        from ...engine.store import Store
        from ...engine.distill import distill
        from . import paths
        from .llm import build_llm
        llm = build_llm()
        personal = Store(paths.personal_root(), index_path=paths.index_path())
        return distill(turns, personal_store=personal, queue_dir=paths.queue_dir(),
                       llm=llm, judge=llm if hasattr(llm, "__call__") else None)

    def on_maintenance(self) -> None:
        from .curate import maybe_curate_in_background
        maybe_curate_in_background()
