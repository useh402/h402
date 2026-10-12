"""Consensus rules per task type. Returns (result, agreement, agrees_flags) or None when undecided."""

from __future__ import annotations

import json
import re
import statistics
from typing import Any


def _norm(v: Any) -> str:
    if isinstance(v, str):
        return re.sub(r"\s+", " ", v.strip().lower())
    if isinstance(v, list):
        return json.dumps(sorted(_norm(x) for x in v))
    return json.dumps(v, sort_keys=True)


def decide(rule: str, answers: list[dict], workers_wanted: int) -> tuple[dict, float, list[bool]] | None:
    """answers: list of {"answer": ..., "note": ...}. Decided when enough answers agree."""
    n = len(answers)
    if n == 0:
        return None
    if rule == "single":
        a = answers[0]
        return {"answer": a["answer"], "note": a.get("note", ""), "confidence": a.get("confidence")}, 1.0, [True]

    if rule in ("majority", "match"):
        keys = [_norm(a["answer"]) for a in answers]
        counts: dict[str, int] = {}
        for k in keys:
            counts[k] = counts.get(k, 0) + 1
        best_key, best = max(counts.items(), key=lambda kv: kv[1])
        needed = workers_wanted // 2 + 1 if rule == "majority" else 2
        if workers_wanted == 1:
            needed = 1
        if best < needed:
            # Not decided yet; undecidable once all slots are filled or no key can still reach `needed`.
            return None
        flags = [k == best_key for k in keys]
        winner = next(a for a, f in zip(answers, flags, strict=False) if f)
        notes = [a.get("note", "") for a, f in zip(answers, flags, strict=False) if f and a.get("note")]
        return {"answer": winner["answer"], "note": notes[0] if notes else "", "votes": best, "of": n}, best / n, flags

    if rule == "median":
        scores = []
        for a in answers:
            try:
                scores.append(float(a["answer"]))
            except (TypeError, ValueError):
                scores.append(float("nan"))
        valid = [s for s in scores if s == s]
        if len(valid) < min(workers_wanted, 2) and workers_wanted > 1:
            return None
        if not valid:
            return None
        med = statistics.median(valid)
        flags = [s == s and abs(s - med) <= 1.0 for s in scores]
        return {"answer": med, "scores": valid}, sum(flags) / n, flags
    raise ValueError(f"unknown rule {rule}")


def can_still_decide(rule: str, answers: list[dict], workers_wanted: int) -> bool:
    """False when no further answer could produce a consensus (all slots used, no winner)."""
    if len(answers) < workers_wanted:
        return True
    return decide(rule, answers, workers_wanted) is not None
