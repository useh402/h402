"""The house poster: the platform posts tasks itself, continuously, from a funded pool.

Money: an operator deposits into the escrow wallet on chain and records it here (`deposit`), which
credits the `house` account. Posting a task moves money from `house` into the task's hold. Unfilled or
expired house tasks flow back to `house` instead of a refund row. Workers are paid like any other task.
"""

from __future__ import annotations

import logging
import random
import time

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import ledger
from .catalogue import STARTER_TASKS
from .config import Settings
from .models import Buyer, Payment, Task, new_id, now
from .moderation import classify
from .pricing import TaskRequest, parse_task, quote_task, standard_price
from .tasks import PICTURE_PROOFS

logger = logging.getLogger("humanapi.api.house")

HOUSE = "house"

CITIES = ["Phoenix, AZ", "Chicago, IL", "New York, NY", "Austin, TX", "San Francisco, CA", "Denver, CO", "Atlanta, GA", "Seattle, WA", "Portland, OR", "Los Angeles, CA", "Boston, MA", "Houston, TX", "Miami, FL", "Philadelphia, PA", "Dallas, TX", "Nashville, TN", "Detroit, MI", "Minneapolis, MN", "San Diego, CA", "Washington, DC"]
LIBRARIES = {"Chicago, IL": "Chicago Public Library", "New York, NY": "New York Public Library", "Austin, TX": "Austin Public Library", "Seattle, WA": "Seattle Public Library", "Denver, CO": "Denver Public Library", "Boston, MA": "Boston Public Library", "Los Angeles, CA": "Los Angeles Public Library", "Houston, TX": "Houston Public Library", "Phoenix, AZ": "Phoenix Public Library", "Portland, OR": "Multnomah County Library"}


def _remote_variants() -> list[dict]:
    """Community and research templates turned into concrete, doable remote tasks (research from home)."""
    out: list[dict] = []
    for city in CITIES:
        lib = LIBRARIES.get(city)
        out.append({"type": "do", "title": f"Find three food pantries in {city} with published hours", "location": "Remote", "templateId": "HUM-001", "acceptance": "Three pantries, each with name, address, hours, eligibility if stated, and the source link", "payload": {"category": "community_resources", "instructions": f"Using official or organization websites (for example a food bank's own site or a city page), find three food pantries in {city}. For each, write the name, the address, the published hours, any eligibility rules, and the link you used. Do not use third-party aggregator listings as the only source.", "proof": "text"}, "pricePerWorker": 1_200_000, "timeLimitSeconds": 1800})
        if lib:
            out.append({"type": "do", "title": f"Verify weekend hours for five {lib} branches", "location": "Remote", "templateId": "HUM-002", "acceptance": "Five branches with Saturday and Sunday hours from the library's own site, and any listing that disagrees", "payload": {"category": "community_resources", "instructions": f"Open the {lib} website. Pick five branches and write their published Saturday and Sunday hours. Then search each branch on Google Maps and note any branch where the map hours differ from the library site. Include the links.", "url": "https://www.google.com/search?q=" + lib.replace(" ", "+") + "+branches+hours&gl=us&hl=en", "proof": "text"}, "pricePerWorker": 1_000_000, "timeLimitSeconds": 1800})
        out.append({"type": "do", "title": f"Find official cooling or warming centers in {city}", "location": "Remote", "templateId": "HUM-012", "acceptance": "Official city or county source, at least three centers with address and hours, or a clear statement that none are listed right now", "payload": {"category": "community_resources", "instructions": f"Find the official city or county page for cooling centers (summer) or warming centers (winter) in {city}, whichever applies to the current season. List at least three centers with address and hours, or state clearly that the official page lists none at the moment. Include the link.", "proof": "text"}, "pricePerWorker": 1_000_000, "timeLimitSeconds": 1800})
        out.append({"type": "do", "title": f"Compare coworking day-pass prices in {city}", "location": "Remote", "templateId": "HUM-040", "acceptance": "Three spaces with the current published day-pass price, hours of access, and the link", "payload": {"category": "business_research", "instructions": f"Find three coworking spaces in {city} that publish a day-pass price on their own website. For each, write the name, the day-pass price, the hours a day pass covers, any extra fees mentioned, and the link to the page where the price is shown.", "proof": "text"}, "pricePerWorker": 1_000_000, "timeLimitSeconds": 1800})
        out.append({"type": "do", "title": f"Find free tax-preparation help sites in {city}", "location": "Remote", "templateId": "HUM-016", "acceptance": "At least two official VITA or AARP sites with address, eligibility and how to book, from IRS or partner pages", "payload": {"category": "community_resources", "instructions": f"Using the IRS VITA locator or AARP Foundation Tax-Aide site, find at least two free tax-preparation sites in {city}. Write the name, address, who is eligible, whether an appointment is needed, and the link. If the season is closed, say what the page says about reopening.", "url": "https://irs.treasury.gov/freetaxprep/", "proof": "text"}, "pricePerWorker": 1_000_000, "timeLimitSeconds": 1800})
    return out


def catalogue() -> list[dict]:
    from .catalogue_more import more_tasks
    from .manual_tasks import manual_tasks
    from .photo_tasks import dollar_tasks, photo_tasks

    base = [dict(t) for t in STARTER_TASKS]
    return base + manual_tasks() + more_tasks() + _remote_variants() + photo_tasks() + dollar_tasks()


def house_buyer(session: Session, rail: str) -> Buyer:
    b = session.scalars(select(Buyer).where(Buyer.rail == rail, Buyer.payer == HOUSE)).first()
    if b is None:
        b = Buyer(id=new_id("by"), rail=rail, payer=HOUSE, name="H402")
        session.add(b)
        session.flush()
    return b


def balance(session: Session, rail: str) -> int:
    return ledger.balance(session, rail, HOUSE)


def deposit(session: Session, rail: str, amount: int, transaction: str, memo: str = "") -> dict:
    if amount <= 0:
        raise ValueError("amount must be positive")
    ledger.post(session, rail, "escrow", HOUSE, amount, memo=f"house deposit {transaction} {memo}".strip())
    return {"rail": rail, "deposited": amount, "houseBalance": balance(session, rail), "transaction": transaction}


def spent_today(session: Session, rail: str) -> int:
    since = now() - 86400
    rows = session.scalars(select(Task).join(Payment, Payment.id == Task.payment_id).where(Payment.payer == HOUSE, Payment.rail == rail, Task.created_at >= since)).all()
    return sum(t.price_per_worker * t.workers_wanted + t.fee for t in rows if t.chain_state != "listed")  # a listed task has cost nothing yet


def open_house_titles(session: Session, rail: str) -> set[str]:
    rows = session.scalars(select(Task).join(Payment, Payment.id == Task.payment_id).where(Payment.payer == HOUSE, Payment.rail == rail, Task.state.in_(("paid", "open", "claimed", "submitted")))).all()
    return {t.title for t in rows}


def open_house_by_template(session: Session, rail: str) -> dict[str, int]:
    rows = session.scalars(select(Task).join(Payment, Payment.id == Task.payment_id).where(Payment.payer == HOUSE, Payment.rail == rail, Task.state.in_(("paid", "open", "claimed", "submitted")))).all()
    out: dict[str, int] = {}
    for t in rows:
        key = t.template_id or (t.title or "")
        out[key] = out.get(key, 0) + 1
    return out


MAX_OPEN_PER_TEMPLATE = 2


def open_house_count(session: Session, rail: str) -> int:
    return session.scalar(select(func.count()).select_from(Task).join(Payment, Payment.id == Task.payment_id).where(Payment.payer == HOUSE, Payment.rail == rail, Task.state.in_(("paid", "open", "claimed", "submitted")))) or 0


def post_tasks(session: Session, settings: Settings, reqs: list[TaskRequest], rail: str) -> list[Task]:
    """Create house tasks paid from the house balance (no chain payment; the money is already in escrow)."""
    from .tasks import create_tasks

    total = sum(quote_task(r, settings.platform_fee_bps)["total"] for r in reqs)
    listed = bool(settings.escrow_contract) and settings.escrow_lock_on_claim and rail == "robinhood"
    if not listed and balance(session, rail) < total:
        raise ValueError("house balance too low")
    payment = Payment(id=new_id("pay"), rail=rail, network=_network(settings, rail), asset=_asset(settings, rail), payer=HOUSE, pay_to=_pay_to(settings, rail), amount=total, transaction=f"house:{new_id('h')}", quote_id="house")
    session.add(payment)
    session.flush()
    # The money moves from the house account into the payer-style flow create_tasks expects.
    if not listed:
        ledger.post(session, rail, HOUSE, f"payer:{HOUSE}", total, payment_id=payment.id, memo="house funding")
    buyer = house_buyer(session, rail)
    return create_tasks(session, settings, reqs, payment, buyer, None, None)


def round_(session: Session, settings: Settings) -> dict:
    rail = settings.house_rail
    out = {"posted": 0, "skipped": "", "houseBalance": balance(session, rail)}
    if open_house_count(session, rail) >= settings.house_max_open:
        out["skipped"] = "enough open"
        return out
    if spent_today(session, rail) >= settings.house_daily_budget:
        out["skipped"] = "daily budget reached"
        return out
    live = open_house_titles(session, rail)
    per_template = open_house_by_template(session, rail)
    pool = [c for c in catalogue() if (c.get("title") or parse_task(c).title) not in live]
    random.shuffle(pool)
    picks: list[TaskRequest] = []
    pictures = 0
    requesters = ["claude", "chatgpt", "gemini", "grok", "deepseek"]
    for c in pool:
        try:
            r = parse_task({"timeLimitSeconds": 1800, "requester": requesters[(open_house_count(session, rail) + len(picks)) % len(requesters)], **c})
            # A catalogue entry with its own price keeps it; the others get the standard reward.
            update: dict = {"pricePerWorker": max(settings.min_reward, c.get("pricePerWorker") or standard_price(r)), "listSeconds": settings.house_list_seconds}
            n = settings.second_worker_every
            if r.type == "do" and n > 0 and sum(map(ord, r.title)) % n == 0:
                update["workers"] = 2  # a second person does the same task independently, as a cross-check
            r = r.model_copy(update=update)
        except ValueError as e:
            logger.warning("house catalogue entry skipped: %s", e)
            continue
        decision, why = classify(settings, r.type, r.payload)
        if decision == "reject":  # the pool's own catalogue is reviewed by the operator already; only outright rejections stop a post
            logger.warning("house catalogue entry held back by moderation (%s): %s", why, r.title)
            continue
        key = r.templateId or (r.title or "")  # hand-written tasks are each their own kind
        if r.title in {p.title for p in picks} or per_template.get(key, 0) >= MAX_OPEN_PER_TEMPLATE:
            continue  # keep the board varied: at most two open tasks from the same template
        if r.type == "do" and (r.payload or {}).get("proof", "text") in PICTURE_PROOFS:
            if pictures >= settings.house_pictures_per_batch:
                continue  # the rest of the batch is typed work; pictures are checked by hand, one at a time
            pictures += 1
        per_template[key] = per_template.get(key, 0) + 1
        picks.append(r)
        if len(picks) >= settings.house_batch_size:
            break
    if not picks:
        out["skipped"] = "nothing new to post"
        return out
    try:
        tasks = post_tasks(session, settings, picks, rail)
    except ValueError as e:
        out["skipped"] = str(e)
        return out
    out["posted"] = len(tasks)
    out["houseBalance"] = balance(session, rail)
    return out


def status(session: Session, settings: Settings) -> dict:
    rail = settings.house_rail
    return {"enabled": settings.house_poster_enabled, "rail": rail, "houseBalance": balance(session, rail), "openHouseTasks": open_house_count(session, rail), "spentToday": spent_today(session, rail), "dailyBudget": settings.house_daily_budget, "intervalSeconds": settings.house_interval_seconds, "catalogueSize": len(catalogue())}


def _rail(settings: Settings, rail: str) -> dict:
    for r in settings.rails():
        if r["name"] == rail:
            return r
    raise ValueError(f"rail {rail} is not enabled")


def _network(settings: Settings, rail: str) -> str:
    return _rail(settings, rail)["network"]


def _asset(settings: Settings, rail: str) -> str:
    return _rail(settings, rail)["asset"]


def _pay_to(settings: Settings, rail: str) -> str:
    return _rail(settings, rail)["pay_to"]


__all__ = ["HOUSE", "balance", "deposit", "round_", "status", "catalogue", "post_tasks", "house_buyer", "time"]
