"""Task types, base prices and quotes. Prices are per worker in atomic units (6 decimals)."""

from __future__ import annotations

import json
import re
from typing import Any

from pydantic import BaseModel, Field, ValidationError, field_validator

TASK_TYPES: dict[str, dict[str, Any]] = {
    "choose": {"base": 100_000, "workers": 3, "allowed_workers": (1, 2, 3), "time_limit": 120, "rule": "majority"},
    "verify": {"base": 80_000, "workers": 3, "allowed_workers": (1, 2, 3), "time_limit": 120, "rule": "majority"},
    "rate": {"base": 50_000, "workers": 3, "allowed_workers": (1, 2, 3), "time_limit": 120, "rule": "median"},
    "read": {"base": 200_000, "workers": 2, "allowed_workers": (1, 2, 3), "time_limit": 300, "rule": "match"},
    "label": {"base": 50_000, "workers": 3, "allowed_workers": (1, 2, 3), "time_limit": 120, "rule": "majority"},
    "answer": {"base": 500_000, "workers": 1, "allowed_workers": (1,), "time_limit": 900, "rule": "single", "min_reputation": 0.9},
    # Action tasks: one person does something (fill a form, check a page, confirm a listing) and submits proof.
    # The client accepts the proof or raises a dispute within the acceptance window; otherwise it is accepted.
    "do": {"base": 1_000_000, "workers": 1, "allowed_workers": (1, 2), "time_limit": 1800, "rule": "proof", "min_reputation": 0.8, "accept_window": 3600},
}
PROOF_KINDS = ("text", "screenshot", "both", "photos")  # photos: one to three pictures taken on the spot with the camera, with a capture code in the shot
MAX_PRICE_PER_WORKER = 50_000_000  # 50.00
MAX_PAYLOAD_BYTES = 64_000


DIFFICULTIES = ("easy", "medium", "hard")
REQUESTERS = {"claude": "Claude", "chatgpt": "ChatGPT", "gemini": "Gemini", "grok": "Grok", "deepseek": "DeepSeek"}
US_STATES = {"AL", "AK", "AZ", "AR", "CA", "CO", "CT", "DE", "FL", "GA", "HI", "ID", "IL", "IN", "IA", "KS", "KY", "LA", "ME", "MD", "MA", "MI", "MN", "MS", "MO", "MT", "NE", "NV", "NH", "NJ", "NM", "NY", "NC", "ND", "OH", "OK", "OR", "PA", "RI", "SC", "SD", "TN", "TX", "UT", "VT", "VA", "WA", "WV", "WI", "WY", "DC"}


# Tasks are for the United States only. Anything that names India (places, money, apps, documents, phone prefix) is refused.
NOT_US = re.compile(
    r"\b(india|indian|mumbai|bombay|delhi|bengaluru|bangalore|hyderabad|chennai|kolkata|pune|ahmedabad|jaipur|lucknow|gurgaon|gurugram|noida|kerala|"
    r"rupees?|inr|aadhaar|aadhar|pan card|upi|paytm|phonepe|flipkart|zomato|swiggy|irctc|gstin|pincode|lakhs?|crores?|hindi)\b|₹|\+91[\s-]?\d",
    re.IGNORECASE,
)


def us_only(text: str) -> None:
    m = NOT_US.search(text)
    if m:
        raise ValueError(f"tasks are for the United States only (found '{m.group(0)}')")


def normalize_location(value: str | None) -> str:
    """'Remote' or 'City, ST' (United States only)."""
    if not value or value.strip().lower() in ("", "remote", "united states", "us", "usa", "anywhere"):
        return "Remote"
    parts = [p.strip() for p in value.split(",")]
    if len(parts) != 2 or not parts[0] or parts[1].upper() not in US_STATES:
        raise ValueError("location must be 'Remote' or 'City, ST' with a US state code")
    return f"{parts[0].title()}, {parts[1].upper()}"


class TaskRequest(BaseModel):
    type: str
    payload: dict[str, Any]
    title: str | None = Field(default=None, max_length=140)
    location: str | None = Field(default=None, max_length=80)
    acceptance: str | None = Field(default=None, max_length=2000)
    difficulty: str | None = None
    effortMinutes: int | None = Field(default=None, ge=1, le=240)
    templateId: str | None = Field(default=None, max_length=20)
    requester: str | None = Field(default=None, max_length=40)
    workers: int | None = None
    pricePerWorker: int | None = Field(default=None, ge=1, le=MAX_PRICE_PER_WORKER)
    minReputation: float = Field(default=0.0, ge=0.0, le=1.0)
    timeLimitSeconds: int | None = Field(default=None, ge=30, le=10800)  # time to finish once taken; up to three hours for going somewhere
    listSeconds: int | None = Field(default=None, ge=60, le=7 * 86400)  # how long the task stays on the board; default: the time limit
    webhook: dict[str, str] | None = None
    reference: str | None = Field(default=None, max_length=120)

    @field_validator("type")
    @classmethod
    def _type(cls, v: str) -> str:
        if v not in TASK_TYPES:
            raise ValueError(f"unknown task type {v!r}; one of {', '.join(TASK_TYPES)}")
        return v

    @field_validator("payload")
    @classmethod
    def _payload(cls, v: dict) -> dict:
        import json

        if len(json.dumps(v)) > MAX_PAYLOAD_BYTES:
            raise ValueError("payload too large")
        return v

    def normalized(self) -> TaskRequest:
        spec = TASK_TYPES[self.type]
        workers = self.workers or spec["workers"]
        if workers not in spec["allowed_workers"]:
            raise ValueError(f"{self.type} allows workers in {spec['allowed_workers']}")
        price = self.pricePerWorker or spec["base"]
        if price < spec["base"]:
            raise ValueError(f"pricePerWorker below the minimum {spec['base']} for {self.type}")
        min_rep = max(self.minReputation, spec.get("min_reputation", 0.0))
        validate_payload(self.type, self.payload)
        if self.difficulty is not None and self.difficulty not in DIFFICULTIES:
            raise ValueError("difficulty must be easy, medium or hard")
        if self.requester is not None and self.requester.lower() not in REQUESTERS:
            raise ValueError(f"requester must be one of {', '.join(REQUESTERS)}")
        location = normalize_location(self.location)
        title = (self.title or default_title(self.type, self.payload)).strip()[:140]
        effort = self.effortMinutes or {"do": 15, "answer": 5, "read": 2}.get(self.type, 1)
        return self.model_copy(update={"workers": workers, "pricePerWorker": price, "minReputation": min_rep, "timeLimitSeconds": self.timeLimitSeconds or spec["time_limit"], "location": location, "title": title, "difficulty": self.difficulty or ("medium" if self.type == "do" else "easy"), "effortMinutes": effort, "acceptance": (self.acceptance or "").strip(), "requester": self.requester.lower() if self.requester else None})


SHORT_TYPES = ("verify", "choose", "rate", "label")


def standard_price(req: TaskRequest) -> int:
    """The platform's reward for a task, per person. Nothing under $1.50; most work $5 to $20; in-person work up to $50.

    Quick answers: $1.50 plus $0.50 a minute (1 to 3 minutes).   Reading an image: $3.
    Written answers: $5 plus $0.30 a minute (2 to 10 minutes).
    Action tasks: $5 plus $0.30 a minute (5 to 45 minutes), plus $1 for sites that block automation,
    $3 for a phone call, $25 for going somewhere in person. Capped at $50.
    """
    minutes = req.effortMinutes or 0
    category = (req.payload or {}).get("category")
    if req.type in SHORT_TYPES:
        price = 1_500_000 + 500_000 * min(3, max(1, minutes))
    elif req.type == "read":
        price = 3_000_000
    elif req.type == "answer":
        price = 5_000_000 + 300_000 * min(10, max(2, minutes))
    else:
        price = 5_000_000 + 300_000 * min(45, max(5, minutes))
        price += {"blocked_sites": 1_000_000, "calls": 3_000_000, "go_and_see": 25_000_000}.get(category, 0)
    return min(MAX_PRICE_PER_WORKER, max(TASK_TYPES[req.type]["base"], price))


def default_title(kind: str, p: dict) -> str:
    text = str(p.get("question") or p.get("instructions") or p.get("item") or p.get("text") or "")
    first = text.split(".")[0].strip() if text else ""
    if first:
        return first[:140]
    return {"verify": "Check this", "choose": "Pick the best option", "rate": "Rate this", "read": "Read this image", "label": "Tag this item", "answer": "Answer a question", "do": "Do this and show proof"}.get(kind, kind)


def validate_payload(kind: str, p: dict) -> None:
    from .catalogue import CATEGORIES

    if "category" in p and p["category"] not in CATEGORIES:
        raise ValueError(f"payload.category must be one of {', '.join(CATEGORIES)}")
    q = p.get("question")
    if kind in ("choose", "verify", "answer") and not isinstance(q, str):
        raise ValueError("payload.question (string) is required")
    if kind == "choose":
        opts = p.get("options")
        if not isinstance(opts, list) or not 2 <= len(opts) <= 5:
            raise ValueError("payload.options must list 2 to 5 options")
    if kind == "verify" and not (isinstance(p.get("image"), str) or isinstance(p.get("text"), str)):
        raise ValueError("payload.image or payload.text is required")
    if kind == "rate" and not (isinstance(p.get("item"), str) and isinstance(p.get("rubric"), str)):
        raise ValueError("payload.item and payload.rubric are required")
    if kind == "read" and not isinstance(p.get("image"), str):
        raise ValueError("payload.image is required")
    if kind == "label":
        labels = p.get("labels")
        if not isinstance(labels, list) or not 2 <= len(labels) <= 30 or not isinstance(p.get("item"), str):
            raise ValueError("payload.item and payload.labels (2 to 30) are required")
    if kind == "do":
        ins = p.get("instructions")
        if not isinstance(ins, str) or len(ins.strip()) < 20 or len(ins) > 4000:
            raise ValueError("payload.instructions (20 to 4000 characters) is required")
        url = p.get("url")
        if url is not None and not (isinstance(url, str) and url.startswith(("http://", "https://")) and len(url) <= 2000):
            raise ValueError("payload.url must be an http(s) link")
        if p.get("proof", "text") not in PROOF_KINDS:
            raise ValueError("payload.proof must be text, screenshot, both or photos")
        write = p.get("write")
        if write is not None and not (isinstance(write, str) and 3 <= len(write.strip()) <= 300):
            raise ValueError("payload.write (what the person must type alongside the photos) must be 3 to 300 characters")
        geo = p.get("geo")
        if geo is not None:
            ok = isinstance(geo, dict) and isinstance(geo.get("lat"), int | float) and isinstance(geo.get("lng"), int | float) and -90 <= geo["lat"] <= 90 and -180 <= geo["lng"] <= 180
            if not ok:
                raise ValueError("payload.geo must be {lat, lng} of the place to go to")


def quote_task(req: TaskRequest, fee_bps: int) -> dict[str, int]:
    pool = req.pricePerWorker * req.workers  # type: ignore[operator]
    fee = (pool * fee_bps + 9999) // 10000
    return {"workerPool": pool, "fee": fee, "total": pool + fee}


def parse_task(body: dict) -> TaskRequest:
    try:
        req = TaskRequest.model_validate(body).normalized()
        us_only(f"{req.title or ''} {req.location or ''} {json.dumps(req.payload, ensure_ascii=False)}")
        return req
    except ValidationError as e:
        raise ValueError("; ".join(f"{'.'.join(str(x) for x in err['loc'])}: {err['msg']}" for err in e.errors())) from e


def pricing_table(fee_bps: int) -> dict:
    return {
        "platformFeeBps": fee_bps,
        "currency": "USD stablecoin, 6 decimals (atomic units)",
        "types": {
            name: {
                "basePricePerWorker": spec["base"],
                "defaultWorkers": spec["workers"],
                "allowedWorkers": list(spec["allowed_workers"]),
                "timeLimitSeconds": spec["time_limit"],
                "consensus": spec["rule"],
                "minReputation": spec.get("min_reputation", 0.0),
                "exampleTotal": quote_task(TaskRequest(type=name, payload={}).model_copy(update={"workers": spec["workers"], "pricePerWorker": spec["base"]}), fee_bps)["total"],
            }
            for name, spec in TASK_TYPES.items()
        },
    }
