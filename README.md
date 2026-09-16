# Roger Loop — the config-driven test-loop orchestrator

<p align="center">
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT-6366f1?style=flat-square" alt="License"></a>
  <img src="https://img.shields.io/badge/python-3.10%2B-3776ab?style=flat-square&logo=python&logoColor=white" alt="Python 3.10+">
  <img src="https://img.shields.io/badge/dependencies-0-22c55e?style=flat-square" alt="Zero dependencies">
  <img src="https://img.shields.io/badge/providers-any-0ea5e9?style=flat-square" alt="Provider agnostic">
  <img src="https://github.com/Samuelfmedeiros/roger-loop/actions/workflows/tests.yml/badge.svg" alt="CI">
</p>

<p align="center"><strong>Runs your critic → builder → reviewer loop with hard budgets and zero trust in its own memory</strong> — one JSON file configures it, any command-line agent plugs in, and no model provider is baked in.</p>

> 🌐 **English** · [🇧🇷 Português](README.pt-BR.md)

Agentic test loops fail in a way that looks like success. The critic died and the round scored 0, which the loop reads as "code defect"; yesterday's state file answers today's campaign with a 100/100 that was never computed; a gap closed in round 3 flaps open in round 5 and the loop converges anyway; one LLM grading its own argument drifts toward agreement. None of it crashes. All of it ships.

**Roger Loop is the engine those incidents built.** It orchestrates any deterministic critic, any builder, and any reviewer as plain stdin/stdout commands, and every piece of memory it keeps carries proof of where it came from.

## What it guarantees

| Hazard in naive agent loops | Guard here | Module |
|---|---|---|
| Critic output breaks → silent `0` read as a code defect | Contract parser returns `None` + inconclusive; environment rounds never score | `rogerloop/verdict.py` |
| State file outlives its campaign → inherited grade | Fingerprint = git HEAD of `campaign_path` + hash of the critic command; any mismatch archives the state and round 1 really runs | `rogerloop/state.py` |
| Non-git working dir → fingerprint `None` → resume loophole | `None` fingerprint **forbids** resume outright | `rogerloop/state.py` |
| Gap flaps closed → open, loop "converges" | Closed-gap history; reopen stamps `REGRESSION:` in the log | `rogerloop/state.py` |
| Borderline score: accept or burn a round? | Two isolated views (pro/con, fresh context) + a judge; dead leg ⇒ fail toward work, never toward a fake green | `rogerloop/debate.py` |
| Builder/critic output injected into the next prompt | `quarantine()` fences untrusted text as data, strips control chars and forged fences | `rogerloop/verdict.py` |
| Loop runs forever | `max_rounds` + wall-clock `max_minutes`, honoured | `rogerloop/engine.py` |

## The contract

A critic must print, in any order, on stdout:

```
SCORE=<0-100>
GAPS=<gap a|gap b>
DETAIL=<one line>
```

A builder / reviewer / debate leg is **any command** that reads a prompt on
stdin and writes text to stdout — a CLI agent, `curl` to a local model, a
shell script. Nothing here knows about providers, APIs or accounts.

## Quickstart

```bash
git clone https://github.com/Samuelfmedeiros/roger-loop && cd roger-loop
python3 -m rogerloop --selftest          # contract, state guards, e2e, budgets

cp examples/loop.json my-loop.json       # point path/critic/builder at your world
python3 -m rogerloop --config my-loop.json
# STATUS=converged SCORE=100 ROUNDS=2 GAPS=- CAVEATS=- WALL=41s
```

Exit code `0` only when converged; state and timestamped log live in
`$ROGERLOOP_STATE` (default `~/.rogerloop`), one file per campaign name —
never shared.

## Anatomy of a round

```
 critic (deterministic, fenced output)
   score >= gate            -> reviewer sign-off (if configured) -> CONVERGED
   gray_low <= score < gate -> debate:  pro | con -> judge
                                PASS / PASS_WITH_CAVEATS -> CONVERGED
                                REPROVO / INCONCLUSIVE  -> builder round
   score < gate             -> builder round (gaps routed by class)
   score = None             -> environment strike; 2 strikes -> ENV_BROKEN
```

## Why it exists (and where it came from)

This engine is the generalised core of a test loop that has run real
deliveries across many projects since mid-2025 — including its own
maintenance: every guard in the table above exists because its incident
happened once, was diagnosed from logs, and then became a unit test. It is
the sibling of [roger-mlops](https://github.com/Samuelfmedeiros/roger-mlops),
which covers the runtime side of long GPU training; both share the
`SCORE=/GAPS=/DETAIL=` contract and neither knows what model you use.

## Tests

```bash
python3 -m unittest discover -s tests -v
```

Covers the parser (clamp, missing contract, `0 passed`), inherited-grade
archival on fingerprint and critic-source change, non-git resume ban,
flapping-gap regression, fence forgery, converge/budget/env-broken campaign
endings, and config validation.

## License

MIT — see [LICENSE](LICENSE).
