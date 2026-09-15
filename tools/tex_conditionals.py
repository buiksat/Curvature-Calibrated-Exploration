#!/usr/bin/env python3
r"""Resolve the manuscript's one venue switch, and fail closed on the rest.

Two internal tools need the same answer to the same question: *which bytes does
this entry point actually compile?*  `paper/validate.py` needs it so that a
reference living only in the branch a venue does not typeset is not reported as
unresolved, and `submissions/tmlr_2026/package.py` needs it so that a shrink
mechanism cannot hide in a branch the checker was told to skip.

`\iflegacyextras` is the only switch either tool can evaluate: the entry point
sets it, and both branches are written by us.  Every other conditional is
opaque, and an opaque conditional is kept in full.  Guessing which branch
compiles is how a checker gets steered -- an independent reviewer hid
`\scriptsize` behind `\iffalse ... \else \scriptsize \fi` inside the submission
branch, and a parser that credited the inner `\else` to the outer
`\iflegacyextras` dropped the rest of the file and called it clean.

It ships with the supplement because the shipped numerical ledger imports it:
the ledger has to read the same visible bytes a reviewer reads, and duplicating
this parser so one copy could stay unshipped would be two parsers to keep in
agreement.  It carries no repository, host or author information.
"""

from __future__ import annotations

import re

SWITCH = "legacyextras"

#: A TeX control word, lexed the way TeX lexes one: a backslash followed by a
#: maximal run of letters.  Matching a fixed list with `\b` instead got `\ifnum`
#: wrong -- `\ifnum1=1` has no word boundary after the name -- and a missed
#: opener turns the next `\else` into a spurious "outside any conditional".
#: The first alternative swallows a `\newif` declaration, which opens nothing.
_TOKEN = re.compile(r"\\newif\s*\\[a-zA-Z@]+|\\([a-zA-Z@]+)")

_BRANCH = {"else", "or", "fi"}

_SET_TRUE = re.compile(rf"\\{SWITCH}true\b")
_SET_FALSE = re.compile(rf"\\{SWITCH}false\b")


class UnbalancedConditional(ValueError):
    """Raised instead of returning a silently truncated document."""


def strip_comments(text: str) -> str:
    r"""Drop everything after an unescaped ``%`` on each line.

    A literal is only a claim if a reader can see it.  Matching against bytes
    that include comments let a visible number be changed while the old one
    stayed behind in a comment to satisfy the check.
    """

    out = []
    for line in text.splitlines():
        kept, escaped = [], False
        for char in line:
            if char == "%" and not escaped:
                break
            kept.append(char)
            escaped = char == "\\" and not escaped
        out.append("".join(kept))
    return "\n".join(out)


def switch_value(text: str, *, default: bool) -> bool:
    r"""Read `\legacyextrastrue` / `\legacyextrasfalse` out of an entry point."""

    last_true = max((m.start() for m in _SET_TRUE.finditer(text)), default=-1)
    last_false = max((m.start() for m in _SET_FALSE.finditer(text)), default=-1)
    if last_true < 0 and last_false < 0:
        return default
    return last_true > last_false


def resolve(text: str, *, legacy: bool) -> str:
    r"""Return the text an entry point with this switch value compiles.

    Raises `UnbalancedConditional` rather than returning a truncated string,
    because a truncated string is a silent hole in whatever check reads it.
    """

    out: list[str] = []
    # Each frame is (kind, taking).  `taking` is meaningful only for "switch";
    # an "opaque" frame never suppresses text, so both of its branches are kept.
    stack: list[tuple[str, bool]] = []

    def keeping() -> bool:
        return all(taking for kind, taking in stack if kind == "switch")

    position = 0
    for match in _TOKEN.finditer(text):
        name = match.group(1)
        if name is None:
            # a `\newif` declaration: consumed, opens nothing
            if keeping():
                out.append(text[position:match.end()])
            position = match.end()
            continue
        if not (name == f"if{SWITCH}" or name.startswith("if")
                or name in _BRANCH):
            continue                      # an ordinary control word
        if keeping():
            out.append(text[position:match.start()])
        position = match.end()
        if name == f"if{SWITCH}":
            stack.append(("switch", legacy))
        elif name.startswith("if"):
            stack.append(("opaque", True))
        elif name in ("else", "or"):
            if not stack:
                raise UnbalancedConditional(
                    f"\\{name} outside any conditional")
            kind, taking = stack[-1]
            if kind == "switch" and name == "else":
                stack[-1] = (kind, not taking)
        else:                             # \fi
            if not stack:
                raise UnbalancedConditional("\\fi outside any conditional")
            stack.pop()
    if keeping():
        out.append(text[position:])
    if stack:
        raise UnbalancedConditional(
            f"unbalanced conditional: {len(stack)} branch(es) left open "
            f"({[kind for kind, _ in stack]})")
    return "".join(out)
