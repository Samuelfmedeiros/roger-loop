"""The verdict contract: SCORE= / GAPS= / DETAIL=.

Every critic in the Roger family, however it is implemented, must end its
stdout with these lines:

    SCORE=<0-100>
    GAPS=<a|b|c>            (empty between bars if none)
    DETAIL=<one line>

Parsing rules that came out of real incidents (see roger-mlops hygiene):
- missing SCORE= is NOT a zero — it returns None and the caller logs an
  environment failure; grading a broken critic as 0 hides dead infrastructure
  behind a fake code defect.
- "0 passed" style output means the environment died, not the code: the
  round is marked inconclusive and never scores.
- critic text is UNTRUSTED until fenced: control characters and forged
  fences are neutralised before it can reach any builder prompt.
"""
from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from typing import List, Optional

_SCORE_RE = re.compile(r"(?:^|\s)SCORE\s*=\s*(\d{1,3})\b", re.M)
_GAPS_RE = re.compile(r"(?:^|\s)GAPS\s*=\s*(.*)$", re.M)
_DETAIL_RE = re.compile(r"(?:^|\s)DETAIL\s*=\s*(.*)$", re.M)

# OWASP Agentic LLM01: tool/critic output is data, never instructions.
_FENCE = "<<<UNTRUSTED_DATA>>>"
_CLOSE = "<<<END_UNTRUSTED_DATA>>>"
_CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\u200b-\u200f\u2028\u2029]")
_MAX = 8000

GAP_CLASS = {
    "test": ("test", "tests", "pytest", "unittest", "coverage"),
    "lint": ("lint", "ruff", "flake", "mypy", "prettier", "eslint"),
    "security": ("security", "vuln", "cve", "secret", "injection", "xss"),
    "ui": ("ui", "visual", "screenshot", "layout", "contrast", "responsive"),
    "perf": ("perf", "slow", "timeout", "memory", "leak", "bench"),
}


def quarantine(text: str, label: str = "tool-output") -> str:
    """Wrap untrusted text so it cannot pose as instructions to a builder."""
    t = _CTRL_RE.sub("", text or "")
    t = t.replace(_FENCE, "<fence>").replace(_CLOSE, "<end-fence>")
    if len(t) > _MAX:
        t = t[:_MAX] + "\n…[truncated]"
    return f"{_FENCE} source={label}\n{t}\n{_CLOSE}"


def gap_class(gap: str) -> str:
    g = (gap or "").lower()
    for cls, needles in GAP_CLASS.items():
        if any(n in g for n in needles):
            return cls
    return "code"


@dataclass
class Verdict:
    score: Optional[int]
    gaps: List[str] = field(default_factory=list)
    detail: str = ""
    inconclusive: bool = False
    raw_hash: str = ""

    @property
    def graded(self) -> bool:
        return self.score is not None and not self.inconclusive

    def routes(self) -> dict:
        out: dict = {}
        for g in self.gaps:
            out.setdefault(gap_class(g), []).append(g)
        return out


def parse_critic_output(text: str) -> Verdict:
    """Never returns 0 for a broken critic; returns score=None instead."""
    t = text or ""
    env_dead = bool(re.search(r"\b0 passed\b|\bno tests ran\b|ModuleNotFound", t, re.I))
    m = _SCORE_RE.search(t)
    if m is None:
        return Verdict(score=None, detail="critic quebrou o contrato SCORE=",
                       inconclusive=True, raw_hash=hashlib.sha256(t.encode()).hexdigest()[:12])
    score = max(0, min(100, int(m.group(1))))
    gm = _GAPS_RE.search(t)
    gaps = [g.strip() for g in gm.group(1).strip("|").split("|") if g.strip()] if gm else []
    dm = _DETAIL_RE.search(t)
    detail = (dm.group(1).strip() if dm else "")[:400]
    return Verdict(score=score, gaps=gaps, detail=detail,
                   inconclusive=env_dead,
                   raw_hash=hashlib.sha256(t.encode()).hexdigest()[:12])
