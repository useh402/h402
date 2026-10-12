"""Pre-routing moderation. Rules first (cheap, explainable), then an optional external classifier.

Decisions: allow (route), review (hold for a human), reject (refund in full).
"""

from __future__ import annotations

import json
import logging
import re

import httpx

from .config import Settings

logger = logging.getLogger("humanapi.api.moderation")

REJECT_RULES: list[tuple[str, re.Pattern]] = [
    ("credentials", re.compile(r"\b(password|passcode|otp|2fa code|one[- ]time code|api[_ -]?key|secret key|private key|seed phrase|recovery phrase|mnemonic)\b", re.I)),
    ("captcha", re.compile(r"\b(captcha|recaptcha|hcaptcha|solve (this|the) (puzzle|challenge)|prove you are (not a robot|human))\b", re.I)),
    ("account_access", re.compile(r"\b(log ?in to|sign ?in to|access) (my|the|their|his|her) (account|email|bank|wallet)\b", re.I)),
    ("sexual_minors", re.compile(r"\b(child|minor|underage|teen)\b.{0,40}\b(nude|sex|porn|explicit)\b|\b(nude|sex|porn|explicit)\b.{0,40}\b(child|minor|underage|teen)\b", re.I | re.S)),
    ("violence", re.compile(r"\b(how to (kill|poison|hurt|attack)|make a (bomb|weapon)|plan (an|the) (attack|shooting))\b", re.I)),
]
REVIEW_RULES: list[tuple[str, re.Pattern]] = [
    ("phone_number", re.compile(r"(?<!\d)(\+?\d[\d\s().-]{8,}\d)(?!\d)")),
    ("email", re.compile(r"[\w.+-]+@[\w-]+\.[\w.]+")),
    ("private_person", re.compile(r"\b(home address|where (does|do) .{1,40} live|find (the )?(address|location) of|track (him|her|them|this person)|real name of)\b", re.I)),
    ("sexual", re.compile(r"\b(porn|nude|nsfw|sexual|explicit)\b", re.I)),
    ("identity_document", re.compile(r"\b(passport|driver'?s licen[cs]e|state id|ssn|social security|green card)\b", re.I)),
    ("hate", re.compile(r"\b(kill all|exterminate|subhuman)\b", re.I)),
    ("money_action", re.compile(r"\b(buy|purchase|pay for|check ?out|send money|transfer (funds|money)|wire|deposit|withdraw|place (an|the) order)\b", re.I)),
    ("impersonation", re.compile(r"\b(pretend to be|pose as|on behalf of (me|us) as|use my name)\b", re.I)),
]
HEX_KEY = re.compile(r"\b(0x)?[0-9a-fA-F]{64}\b")
URL = re.compile(r"https?://\S+")
BIP39_RUN = re.compile(r"\b(?:[a-z]{3,8}\s+){11,23}[a-z]{3,8}\b")


def _text_of(payload: dict) -> str:
    parts = []
    for v in payload.values():
        if isinstance(v, str):
            parts.append(v)
        elif isinstance(v, list):
            parts.extend(str(x) for x in v)
    # URLs carry ids and hashes that look like phone numbers or keys; they are not content.
    return URL.sub(" ", "\n".join(parts))


ACTION_ONLY_REVIEW = {"money_action", "impersonation"}  # only matter when a person is asked to act
CALL_CATEGORY_ALLOWS = {"phone_number"}  # a call task needs a business number


def rules(kind: str, payload: dict) -> tuple[str, str]:
    text = _text_of(payload)
    for name, rx in REJECT_RULES:
        if rx.search(text):
            return "reject", name
    if HEX_KEY.search(text) and re.search(r"\b(key|secret|seed|wallet)\b", text, re.I):
        return "reject", "credentials"
    if BIP39_RUN.search(text.lower()) and re.search(r"\b(seed|phrase|recover|wallet)\b", text, re.I):
        return "reject", "credentials"
    category = payload.get("category") if isinstance(payload, dict) else None
    for name, rx in REVIEW_RULES:
        if name in ACTION_ONLY_REVIEW and kind != "do":
            continue  # judging text that mentions buying is not buying
        if name in CALL_CATEGORY_ALLOWS and kind == "do" and category == "calls":
            continue
        if rx.search(text):
            return "review", name
    return "allow", ""


def classify(settings: Settings, kind: str, payload: dict, http: httpx.Client | None = None) -> tuple[str, str]:
    decision, reason = rules(kind, payload)
    if decision == "reject" or not settings.moderation_url:
        return decision, reason
    try:
        client = http or httpx.Client(timeout=8)
        r = client.post(settings.moderation_url, json={"type": kind, "payload": payload})
        data = r.json() if r.status_code < 400 else {}
        ext = data.get("decision")
        if ext in ("reject", "review") and (ext == "reject" or decision == "allow"):
            return ext, f"classifier:{data.get('reason', '')}"[:200]
    except Exception as e:
        logger.warning("moderation classifier unavailable: %s", str(e)[:200])
        if decision == "allow":
            return "review", "classifier_unavailable"
    return decision, reason


__all__ = ["classify", "rules", "json"]
