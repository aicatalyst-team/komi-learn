"""komi-learn — distiller/judge backed by the local ``claude`` CLI (OAuth session).

This lets the background distiller use the user's existing Claude.ai subscription
auth instead of a separate ANTHROPIC_API_KEY, by shelling out to the ``claude``
CLI in headless mode (``claude -p``). It implements the same ``LLMClient`` /
``ScopeJudge`` interface as the API-backed client.

Robustness is the priority: a detached hook may not always have a working auth
context, so every failure (CLI missing, auth error, timeout, junk output) returns
an empty / conservative result rather than raising. The loop then degrades to
"recall works, distill no-ops this turn" — never a crash, never a blocked session.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from typing import Optional

from ...engine.model import Learning, Scope


# Marker substrings that mean "auth/access failed" rather than "model said this".
_AUTH_FAIL_MARKERS = (
    "does not have access",
    "Please login",
    "Invalid API key",
    "authentication",
    "Unauthorized",
)


class ClaudeCLILLM:
    """LLMClient + ScopeJudge backed by ``claude -p``.

    Parameters
    ----------
    model : alias like "haiku"/"sonnet" or a full model id. Distillation is a
        summarization task, so a small model is the sensible default.
    timeout : per-call seconds; a stuck CLI must never hang a hook.
    """

    def __init__(self, *, model: str = "haiku", timeout: int = 90,
                 claude_bin: Optional[str] = None):
        self.model = model
        self.timeout = timeout
        self.claude_bin = claude_bin or shutil.which("claude") or "claude"
        self._healthy = shutil.which(self.claude_bin) is not None or os.path.exists(self.claude_bin)

    @property
    def available(self) -> bool:
        return self._healthy

    def _run(self, *, system: str, user: str, max_tokens_hint: int = 2000) -> str:
        """One headless call. Returns model text, or "" on any failure."""
        if not self._healthy:
            return ""
        cmd = [
            self.claude_bin, "-p",
            "--output-format", "text",
            "--model", self.model,
            "--no-session-persistence",
            "--append-system-prompt", system,
        ]
        try:
            proc = subprocess.run(
                cmd, input=user, capture_output=True, text=True,
                timeout=self.timeout,
                # Keep the distiller from inheriting hook-specific env that could
                # change behavior; pass through auth-relevant vars only.
                env=_clean_env(),
            )
        except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
            return ""
        out = (proc.stdout or "").strip()
        if proc.returncode != 0 and not out:
            return ""
        # Detect auth/access failures that the CLI prints as normal stdout.
        if any(m.lower() in out.lower() for m in _AUTH_FAIL_MARKERS) and len(out) < 300:
            return ""
        return out

    # LLMClient ----------------------------------------------------------------

    def complete(self, *, system: str, user: str) -> str:
        return self._run(system=system, user=user)

    # ScopeJudge ---------------------------------------------------------------

    def __call__(self, learning: Learning, *, context: dict) -> dict:
        usr = json.dumps({
            "title": learning.title, "body": learning.body,
            "trigger": learning.trigger, "tags": learning.tags,
            "category": learning.category, "cwd": context.get("cwd", ""),
        }, ensure_ascii=False)
        text = self._run(system=_JUDGE_SYSTEM, user=usr, max_tokens_hint=800)
        if not text:
            return {"scope": Scope.PROJECT.value, "category": learning.category,
                    "rationale": "judge-unavailable"}
        start, end = text.find("{"), text.rfind("}")
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(text[start:end + 1])
            except json.JSONDecodeError:
                pass
        return {"scope": Scope.PROJECT.value, "category": learning.category,
                "rationale": "judge-unparseable"}


def _clean_env() -> dict:
    """Environment for the CLI subprocess. We strip hook-injected CLAUDE_CODE_*
    vars that could make the nested CLI think it's inside a hook, but keep PATH,
    HOME, and auth/credential locations so OAuth/keychain still resolve."""
    keep_prefixes = ("PATH", "HOME", "USERPROFILE", "APPDATA", "LOCALAPPDATA",
                     "SystemRoot", "TEMP", "TMP", "ANTHROPIC_API_KEY",
                     "ANTHROPIC_BASE_URL", "CLAUDE_CONFIG_DIR")
    env = {}
    for k, v in os.environ.items():
        if k.startswith(keep_prefixes):
            env[k] = v
    # Explicitly DROP CLAUDE_CODE_* / CLAUDECODE so the nested CLI runs clean.
    return env


_JUDGE_SYSTEM = """You decide the SCOPE of a distilled learning for a shared knowledge system.

Given one learning (JSON), decide whether it is GENERALLY TRUE and useful to anyone
doing this class of work — independent of this specific user, project, or machine —
or whether it is specific to this project's conventions.

Return ONLY a JSON object:
{
  "scope": "global" | "project",
  "category": "<keep or refine the category>",
  "generalized_title": "<if global: rewrite title to be general, stripping any project/user/machine specifics>",
  "generalized_body": "<if global: rewrite body to be general; remove any names, paths, identifiers>",
  "rationale": "<one short clause>"
}

Rules:
- "global" ONLY if the lesson holds for many people and contains NO identifiers,
  names, paths, repo/org names, or anything user/machine-specific. When unsure → "project".
- Be conservative: a wrong "global" leaks specifics into a public pool. Default "project"."""


__all__ = ["ClaudeCLILLM"]
