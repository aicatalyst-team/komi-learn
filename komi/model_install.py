"""komi-learn — install the local semantic-recall model on the user's behalf.

The whole point: a user should never have to know `pip install komi-learn[smart]`
or what "sentence-transformers" is. The wizard asks "enable smarter memory?" and
this runs the install with a clear size warning + progress. If it fails, recall
just keeps using keyword search — no breakage.
"""

from __future__ import annotations

import subprocess
import sys


def semantic_available() -> bool:
    try:
        from .engine import embed
        embed._reset_cache_for_tests()  # re-probe in case it was just installed
        return embed.available()
    except Exception:
        return False


def is_installed() -> bool:
    """True if the sentence-transformers library is importable (model may still
    need a one-time download on first use)."""
    try:
        import sentence_transformers  # noqa: F401
        return True
    except Exception:
        return False


def install_model(*, quiet: bool = False) -> tuple[bool, str]:
    """pip install the semantic-recall dependency into the running interpreter.
    Returns (ok, detail). The model weights download lazily on first encode."""
    if is_installed():
        return True, "already installed"
    cmd = [sys.executable, "-m", "pip", "install", "sentence-transformers>=2.2"]
    if quiet:
        cmd.append("--quiet")
    try:
        r = subprocess.run(cmd, timeout=1200)
    except subprocess.TimeoutExpired:
        return False, "pip install timed out"
    except Exception as e:
        return False, f"pip install failed to launch: {e}"
    if r.returncode != 0:
        return False, f"pip install exited {r.returncode}"
    return True, "installed"


__all__ = ["semantic_available", "is_installed", "install_model"]
