"""Runner: one prompt in (stdin), one text out (stdout).

The engine never imports a model SDK. A runner is any executable that
follows the stdin/stdout contract — a CLI agent, a curl to a local model,
``cat`` in a test. Failures come back as a RunnerResult, never an
exception: the loop must stay alive when a leg dies.
"""
from __future__ import annotations

import os
import subprocess
from dataclasses import dataclass
from typing import Dict, List, Optional

from .config import Runner


@dataclass
class RunnerResult:
    ok: bool
    text: str = ""
    error: str = ""
    rc: int = 0

    @property
    def failed(self) -> bool:
        return not self.ok


def run(runner: Optional[Runner], prompt: str, cwd: str,
        extra_env: Optional[Dict[str, str]] = None) -> RunnerResult:
    """Execute *runner* with *prompt* on stdin. Never raises."""
    if runner is None:
        return RunnerResult(False, error="runner not configured")
    env = dict(os.environ)
    env.update(extra_env or {})
    try:
        p = subprocess.run(
            runner.command, input=prompt.encode("utf-8"),
            cwd=cwd, env=env, timeout=runner.timeout,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    except subprocess.TimeoutExpired:
        return RunnerResult(False, error=f"timeout {runner.timeout}s")
    except FileNotFoundError as e:
        return RunnerResult(False, error=f"command not found: {e}")
    except OSError as e:
        return RunnerResult(False, error=f"oserror: {e}")
    out = (p.stdout or b"").decode("utf-8", "replace")
    err = (p.stderr or b"").decode("utf-8", "replace").strip()
    if p.returncode != 0:
        return RunnerResult(False, text=out, error=err or f"rc={p.returncode}",
                            rc=p.returncode)
    return RunnerResult(True, text=out, error=err)
