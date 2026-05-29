"""komi-learn - small interactive-prompt helpers for the install wizard + config menu.

Hermes-style: plain one-line explanations and simple Y/n choices, with sensible
defaults. Crucially these are SAFE in non-interactive contexts: if stdin isn't a
TTY (piped, CI, a hook) or ``assume_yes`` is set, they don't block - they return
the default and print what they chose. So `komi-learn install --yes` and scripted
installs Just Work.
"""

from __future__ import annotations

import sys

# Windows consoles default to cp1252 and crash on non-ASCII. Force UTF-8 once at
# import so prompts (and any glyphs) never blow up a user's install. Harmless
# elsewhere. (cli.py does this too; doing it here covers direct imports/tests.)
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

# Module-level switch flipped by --yes / non-interactive detection. When True,
# every prompt resolves to its default without reading stdin.
ASSUME_YES = False


def _interactive() -> bool:
    if ASSUME_YES:
        return False
    try:
        return sys.stdin is not None and sys.stdin.isatty()
    except Exception:
        return False


def say(line: str = "") -> None:
    print(line)


def ask_yes_no(question: str, *, default: bool, summary: str = "") -> bool:
    """Ask a yes/no question. ``summary`` is a one-line plain explanation printed
    above it. ``default`` is used on Enter, in --yes mode, and when non-interactive."""
    if summary:
        say(f"  {summary}")
    suffix = "[Y/n]" if default else "[y/N]"
    if not _interactive():
        say(f"  {question} {suffix}  -> {'yes' if default else 'no'} (default)")
        return default
    while True:
        try:
            ans = input(f"  {question} {suffix} ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            say()
            return default
        if ans == "":
            return default
        if ans in ("y", "yes"):
            return True
        if ans in ("n", "no"):
            return False
        say("    please answer y or n")


def ask_choice(question: str, options: list[tuple[str, str]], *, default: int = 0) -> str:
    """Ask the user to pick one of ``options`` (list of (value, label)). Returns the
    chosen value. Non-interactive -> the default option's value."""
    say(f"  {question}")
    for i, (_, label) in enumerate(options):
        marker = "*" if i == default else " "
        say(f"    {marker} {i + 1}) {label}")
    if not _interactive():
        say(f"    -> {options[default][1]} (default)")
        return options[default][0]
    while True:
        try:
            ans = input(f"  choose [1-{len(options)}] (default {default + 1}): ").strip()
        except (EOFError, KeyboardInterrupt):
            say()
            return options[default][0]
        if ans == "":
            return options[default][0]
        if ans.isdigit() and 1 <= int(ans) <= len(options):
            return options[int(ans) - 1][0]
        say(f"    please enter 1-{len(options)}")


def ask_text(question: str, *, default: str = "", summary: str = "") -> str:
    """Free-text prompt. Non-interactive -> default."""
    if summary:
        say(f"  {summary}")
    if not _interactive():
        say(f"  {question}  -> {default or '(blank)'} (default)")
        return default
    try:
        ans = input(f"  {question}" + (f" [{default}]" if default else "") + ": ").strip()
    except (EOFError, KeyboardInterrupt):
        say()
        return default
    return ans or default


__all__ = ["ASSUME_YES", "say", "ask_yes_no", "ask_choice", "ask_text"]
