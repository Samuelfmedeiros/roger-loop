#!/usr/bin/env python3
"""Minimal deterministic critic that satisfies the Roger contract.

Drop a file like this in your repo, point loop.json's critic.command at it,
and the loop is live. Print SCORE/GAPS/DETAIL and nothing else matters.
"""
import subprocess
import sys

out = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests"],
                     capture_output=True, text=True)
text = out.stdout + out.stderr
score, gaps = 100, []
if out.returncode != 0:
    score -= 60
    gaps.append("test suite failing")
if "Error" in text and out.returncode != 0:
    gaps.append("inspect traceback")
print("DETAIL=unittest discover finished rc=%d" % out.returncode)
print("GAPS=%s" % ("|".join(gaps) if gaps else ""))
print("SCORE=%d" % score)
sys.exit(0)
