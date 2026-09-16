"""Roger Loop configuration.

Everything the engine knows about the world comes from a single JSON file
(``loop.json`` by default). Nothing is hardcoded, no provider, host, or
account is baked in: builders, critics and reviewers are opaque *commands*
that read a prompt from stdin and write text to stdout. That is the seam
that keeps this engine model-agnostic.

Keys
----
name            : str   campaign name (used in state/report filenames)
path            : str   repository the loop works on (git repo preferred)
campaign_path   : str   fingerprint source when `path` is not a git repo
                        (falls back to `path`)
gate            : int   score needed to declare a round converged (default 85)
gray_low        : int   below gate but above this, run the gray-zone debate
max_rounds      : int   hard budget of rounds (default 8)
max_minutes     : int   wall-clock budget for the campaign (default 90)
critic          : {"command": [...], "timeout": int}
builder         : {"command": [...], "timeout": int}   optional fixer
reviewer        : {"command": [...], "timeout": int}   optional second opinion
debate          : {"pro": {...}, "con": {...}, "judge": {...}}  optional
report          : {"command": [...]}  optional renderer; default = built-in MD
env             : dict  extra environment for every runner
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

DEFAULTS: Dict[str, Any] = {
    "gate": 85,
    "gray_low": 70,
    "max_rounds": 8,
    "max_minutes": 90,
}


def _sub(d: Dict[str, Any], key: str) -> Optional[Dict[str, Any]]:
    v = d.get(key)
    return v if isinstance(v, dict) and v.get("command") else None


@dataclass
class Runner:
    """A command line that turns a stdin prompt into stdout text."""

    command: List[str]
    timeout: int = 900

    @staticmethod
    def from_cfg(spec: Optional[Dict[str, Any]]) -> Optional["Runner"]:
        if not spec:
            return None
        cmd = spec.get("command")
        if isinstance(cmd, str):
            cmd = ["sh", "-c", cmd]
        if not cmd:
            return None
        return Runner(command=list(cmd), timeout=int(spec.get("timeout", 900)))


@dataclass
class Config:
    name: str
    path: str
    gate: int = DEFAULTS["gate"]
    gray_low: int = DEFAULTS["gray_low"]
    max_rounds: int = DEFAULTS["max_rounds"]
    max_minutes: int = DEFAULTS["max_minutes"]
    campaign_path: Optional[str] = None
    critic: Optional[Runner] = None
    builder: Optional[Runner] = None
    reviewer: Optional[Runner] = None
    debate: Dict[str, Optional[Runner]] = field(default_factory=dict)
    report: Optional[Runner] = None
    env: Dict[str, str] = field(default_factory=dict)
    source: str = "<defaults>"

    @property
    def effective_campaign_path(self) -> str:
        return self.campaign_path or self.path

    @staticmethod
    def require_critic() -> str:
        return ("config must define critic.command — the loop is nothing "
                "without a deterministic critic")


def load(path: str) -> Config:
    with open(path, encoding="utf-8") as f:
        d = json.load(f)
    if not d.get("name") or not d.get("path"):
        raise ValueError("config requires 'name' and 'path'")
    cfg = Config(
        name=str(d["name"]),
        path=os.path.abspath(os.path.expanduser(str(d["path"]))),
        gate=int(d.get("gate", DEFAULTS["gate"])),
        gray_low=int(d.get("gray_low", DEFAULTS["gray_low"])),
        max_rounds=int(d.get("max_rounds", DEFAULTS["max_rounds"])),
        max_minutes=int(d.get("max_minutes", DEFAULTS["max_minutes"])),
        campaign_path=(os.path.abspath(os.path.expanduser(str(d["campaign_path"])))
                       if d.get("campaign_path") else None),
        critic=Runner.from_cfg(_sub(d, "critic")),
        builder=Runner.from_cfg(_sub(d, "builder")),
        reviewer=Runner.from_cfg(_sub(d, "reviewer")),
        debate={k: Runner.from_cfg(_sub(d.get("debate", {}) or {}, k))
                for k in ("pro", "con", "judge")},
        report=Runner.from_cfg(_sub(d, "report")),
        env={str(k): str(v) for k, v in (d.get("env") or {}).items()},
        source=os.path.abspath(os.path.expanduser(path)),
    )
    if cfg.critic is None:
        raise ValueError(Config.require_critic())
    if not (0 < cfg.gate <= 100):
        raise ValueError("gate must be in (0, 100]")
    if cfg.gray_low >= cfg.gate:
        raise ValueError("gray_low must be below gate")
    return cfg
