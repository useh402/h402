"""The gate: a task that a chatbot can finish on its own is not worth paying a person for.

Before a task is posted, one model is asked to do it with nothing but the task text. If it produces a confident,
complete answer, the task is refused. Tasks that need a photo taken now, a call, a visit, or a page the model is not
allowed to open pass, because the answer is not in the text.
"""

from __future__ import annotations

import json
import logging
import re

import httpx

from .config import Settings

logger = logging.getLogger("humanapi.api.gate")

PROMPT = (
    "You are checking whether a task needs a real person. Try to complete the task below using only what is written in it. "
    "Then answer with JSON only: {\"canDo\": true|false, \"answer\": \"your answer or empty\", \"reason\": \"one short sentence\"}. "
    "Say canDo true only when you can give the complete, correct result right now with confidence, without visiting a place, "
    "calling anyone, taking a photo, logging in, opening a site you cannot access, or knowing something that happened after your training. "
    "Arithmetic, dates, spelling, reading clean text, general knowledge and judging text you are given all count as canDo true."
)

NEEDS_PERSON = ("photo", "photograph", "call ", "phone", "visit", "go to", "in person", "take a picture", "screenshot of your", "logged in", "your account")


def chatbot_can_do(settings: Settings, http: httpx.Client, title: str, payload: dict) -> tuple[bool, str]:
    """(True, reason) when a chatbot could finish the task alone and it should be refused."""
    text = json.dumps({"title": title, **{k: v for k, v in payload.items() if k in ("question", "text", "instructions", "item", "options", "labels", "rubric", "url", "proof")}}, ensure_ascii=False)
    if payload.get("proof") in ("photos", "screenshot", "both") and any(w in text.lower() for w in NEEDS_PERSON):
        return False, "needs a photo, a call or a visit"
    if not settings.ai_gateway_api_key:
        return False, "gate not configured"
    try:
        r = http.post(
            f"{settings.ai_gateway_base_url}/chat/completions",
            headers={"Authorization": f"Bearer {settings.ai_gateway_api_key}"},
            json={"model": settings.gate_model, "messages": [{"role": "system", "content": PROMPT}, {"role": "user", "content": text[:6000]}], "temperature": 0, "max_tokens": 300},
            timeout=60,
        )
        r.raise_for_status()
        content = r.json()["choices"][0]["message"]["content"]
        m = re.search(r"\{.*\}", content, re.S)
        verdict = json.loads(m.group(0)) if m else {}
    except Exception as e:
        logger.warning("gate call failed: %s", str(e)[:200])
        return False, "gate unavailable"
    if verdict.get("canDo") is True:
        return True, f"a chatbot can do this: {str(verdict.get('reason', ''))[:160]}"
    return False, str(verdict.get("reason", "needs a person"))[:160]
