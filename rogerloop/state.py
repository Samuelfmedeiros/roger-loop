"""Campaign state: fingerprinting, inherited-grade guards, regressions.

Three incidents wrote this file (all real, all cheap to prevent):

1. Inherited grade — a ``.loop-state.json`` shared between projects made a
   new campaign "resume" a 100/100 from another campaign's delivery.
   Fix: state filename is per campaign name AND the state carries the
   campaign fingerprint + the critic source hash. Any mismatch discards the
   grade and round 1 actually runs the critic.

2. Non-git paths — ``git rev-parse`` in a scratch dir returns nothing, the
   fingerprint becomes None and the "legacy state < 12h = resume" branch
   re-admits inherited grades. Fix: ``campaign_path`` config key points at
   the real repo; if the fingerprint is None anyway, resuming is FORBIDDEN.

3. Flapping gaps — a gap closed at round N reopens at N+2 and the loop
   declares convergence anyway. Fix: closed-gap history; reopen stamps an
   explicit ``REGRESSION:`` and blocks a clean convergence.
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import time
from dataclasses import dataclass, field
from typing import List, Optional, Set


def campaign_fingerprint(repo_path: str) -> Optional[str]:
    """Short git HEAD of the campaign, or None if it is not a repo."""
    try:
        p = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"], cwd=repo_path,
            capture_output=True, timeout=10)
        if p.returncode == 0:
            return p.stdout.decode("utf-8", "replace").strip() or None
    except (OSError, subprocess.TimeoutExpired):
        pass
    return None


def source_hash(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8", "replace")).hexdigest()[:12]


def _atomic_write(path: str, payload: str) -> None:
    tmp = path + ".part"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(payload)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


@dataclass
class CampaignState:
    """Mutable campaign memory persisted as JSON. State is never shared."""

    name: str
    dir: str
    campaign: Optional[str] = None      # fingerprint of the repo at start
    critic_hash: str = ""               # hash of the critic contract/source
    round: int = 0
    score: Optional[int] = None
    gaps: List[str] = field(default_factory=list)
    closed_gaps: Set[str] = field(default_factory=set)
    prev_open: Set[str] = field(default_factory=set)
    history: List[dict] = field(default_factory=list)
    regressions: List[str] = field(default_factory=list)
    started: float = field(default_factory=time.time)

    # ---- persistence -----------------------------------------------------
    @property
    def _file(self) -> str:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in self.name)
        return os.path.join(self.dir, f"loop-{safe}.state.json")

    @property
    def _log(self) -> str:
        safe = "".join(c if c.isalnum() or c in "-_." else "_" for c in self.name)
        return os.path.join(self.dir, f"loop-{safe}.log")

    @staticmethod
    def load_or_new(name: str, dir: str, campaign: Optional[str],
                    critic_hash: str, log: callable = None) -> "CampaignState":
        os.makedirs(dir, exist_ok=True)
        path = os.path.join(dir, f"loop-{name}.state.json")
        st = None
        if os.path.exists(path):
            try:
                with open(path, encoding="utf-8") as f:
                    d = json.load(f)
                st = CampaignState(
                    name=name, dir=dir, campaign=d.get("campaign"),
                    critic_hash=d.get("critic_hash", ""), round=d.get("round", 0),
                    score=d.get("score"), gaps=d.get("gaps", []),
                    closed_gaps=set(d.get("closed_gaps", [])),
                    prev_open=set(d.get("prev_open", [])),
                    history=d.get("history", []),
                    regressions=d.get("regressions", []),
                    started=d.get("started", time.time()))
            except (json.JSONDecodeError, OSError):
                st = None
        if st is None:
            st = CampaignState(name=name, dir=dir, campaign=campaign,
                               critic_hash=critic_hash)
        # --- guard 1+2: inherited grade is discarded, not resumed ---------
        mismatch = []
        if st.round > 0 and campaign is None and st.campaign is None:
            mismatch.append("fingerprint indisponivel (path nao-git): resume proibido")
        elif st.campaign != campaign:
            mismatch.append(f"fp {st.campaign} -> {campaign}")
        elif st.critic_hash != critic_hash:
            mismatch.append(f"critic {st.critic_hash} -> {critic_hash}")
        if mismatch:
            stamp = time.strftime("%Y-%m-%d %H:%M:%S")
            st.archive(mismatch[0])
            st = CampaignState(name=name, dir=dir, campaign=campaign,
                               critic_hash=critic_hash)
            st.note(f"{stamp} nota herdada descartada: {mismatch[0]} — RODADA 1 real")
        else:
            st.campaign, st.critic_hash = campaign, critic_hash
        return st

    def archive(self, reason: str) -> None:
        if not os.path.exists(self._file):
            return
        dst = self._file + f".archived-{int(time.time())}"
        try:
            os.replace(self._file, dst)
            self.note(f"estado arquivado ({reason}): {os.path.basename(dst)}")
        except OSError:
            pass

    def note(self, line: str) -> None:
        try:
            os.makedirs(self.dir, exist_ok=True)
            with open(self._log, "a", encoding="utf-8") as f:
                f.write(line.rstrip() + "\n")
        except OSError:
            pass

    def save(self) -> None:
        d = dict(self.__dict__)
        d["closed_gaps"] = sorted(self.closed_gaps)
        d["prev_open"] = sorted(self.prev_open)
        _atomic_write(self._file, json.dumps(d, ensure_ascii=False, indent=1))

    # --- guard 3: regression bookkeeping ----------------------------------
    def record_round(self, verdict, builder_ran: bool) -> List[str]:
        self.round += 1
        self.history.append({
            "round": self.round, "ts": time.strftime("%H:%M:%S"),
            "score": verdict.score, "gaps": list(verdict.gaps),
            "inconclusive": verdict.inconclusive, "builder": builder_ran})
        new_regressions: List[str] = []
        if verdict.graded:
            open_set = set(verdict.gaps)
            newly_closed = self.prev_open - open_set
            reopened = open_set & self.closed_gaps
            for g in sorted(reopened):
                tag = f"REGRESSAO: {g}"
                self.regressions.append(f"r{self.round} {g}")
                new_regressions.append(tag)
            self.closed_gaps = (self.closed_gaps | newly_closed) - open_set
            self.prev_open = open_set
        self.score = verdict.score if verdict.graded else self.score
        self.gaps = list(verdict.gaps)
        self.save()
        return new_regressions

    def minutes_elapsed(self) -> float:
        return (time.time() - self.started) / 60.0
