"""komi-learn — the host Adapter contract.

The engine is host-agnostic; an *adapter* binds it to a specific host (Claude Code
today, Codex/a chat UI/etc. later). Until now the "two-method interface" the docs
promised was aspirational — there was no actual contract, just Claude-Code-specific
entry points. This ABC makes it real, so a second host is a known surface to
implement rather than code to copy.

An adapter owns exactly two responsibilities; everything else is the engine's:

  • recall(context)         → the text block to inject at session start
  • on_session_end(turns)   → run the distiller over a finished session

Host-specific plumbing (reading the host's event payload, spawning the background
distiller, where files live) stays inside the concrete adapter. The engine layer
(`komi.engine.*`) is shared verbatim.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class RecallContext:
    """What an adapter knows about the current moment, passed to recall(). Hosts
    fill what they have; all fields are optional so a minimal host still works."""
    cwd: str = ""
    recent_files: list[str] = field(default_factory=list)
    prompt_hint: str = ""


class Adapter(ABC):
    """The contract every host adapter implements. Two methods — that's the whole
    surface a new host must provide."""

    name: str = "adapter"

    @abstractmethod
    def recall(self, context: RecallContext) -> str:
        """Return the context block to inject at session start (may be empty)."""
        raise NotImplementedError

    @abstractmethod
    def on_session_end(self, turns: list[dict]) -> "object":
        """Distill a finished session (list of {role, text} turns). Returns a
        DistillResult-like object; the caller may ignore it. Must never raise into
        the host — failures degrade to a no-op."""
        raise NotImplementedError

    # Optional lifecycle hooks — default no-ops so simple adapters skip them.
    def on_install(self) -> None:  # pragma: no cover - optional
        """Called when the adapter is being installed into its host."""

    def on_maintenance(self) -> None:  # pragma: no cover - optional
        """Periodic maintenance opportunity (pool sync, curation)."""


__all__ = ["Adapter", "RecallContext"]
