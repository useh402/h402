"""Three sample tasks per type with known answers. Two of three right qualifies the worker for that type."""

from __future__ import annotations

from typing import Any

from .consensus import _norm

SAMPLES: dict[str, list[dict[str, Any]]] = {
    "verify": [
        {"payload": {"text": "Total: $12.40, paid by card, 14 March", "question": "Does the text state a total amount?"}, "answer": "yes"},
        {"payload": {"text": "Thank you for shopping with us!", "question": "Does the text state a total amount?"}, "answer": "no"},
        {"payload": {"text": "Order #4411 shipped", "question": "Does the text mention a delivery date?"}, "answer": "no"},
    ],
    "choose": [
        {"payload": {"question": "Which sentence has no spelling mistake?", "options": ["Recieve the package", "Receive the package"]}, "answer": 1},
        {"payload": {"question": "Which title is shorter?", "options": ["A very long title about everything", "Short title"]}, "answer": 1},
        {"payload": {"question": "Which is a fruit?", "options": ["Carrot", "Apple", "Potato"]}, "answer": 1},
    ],
    "rate": [
        {"payload": {"item": "asdf qwer zxcv", "rubric": "1 unreadable, 5 clear English"}, "answer": 1, "tolerance": 1},
        {"payload": {"item": "Please deliver the parcel before noon on Friday.", "rubric": "1 unreadable, 5 clear English"}, "answer": 5, "tolerance": 1},
        {"payload": {"item": "Pakage deliver pls fridy noon", "rubric": "1 unreadable, 5 clear English"}, "answer": 2, "tolerance": 1},
    ],
    "read": [
        {"payload": {"text_preview": "INVOICE 2031  TOTAL 48.00", "image": "/q/read1.png"}, "answer": "INVOICE 2031 TOTAL 48.00"},
        {"payload": {"text_preview": "Gate B12  Boarding 09:40", "image": "/q/read2.png"}, "answer": "Gate B12 Boarding 09:40"},
        {"payload": {"text_preview": "Lot 7  Row 3", "image": "/q/read3.png"}, "answer": "Lot 7 Row 3"},
    ],
    "label": [
        {"payload": {"item": "The battery died after two days.", "labels": ["complaint", "praise", "question"]}, "answer": ["complaint"]},
        {"payload": {"item": "Does this come in blue?", "labels": ["complaint", "praise", "question"]}, "answer": ["question"]},
        {"payload": {"item": "Best purchase this year!", "labels": ["complaint", "praise", "question"]}, "answer": ["praise"]},
    ],
    "do": [
        {"payload": {"question": "An action task asks you to fill in a public contact form. The form also asks for the client's password. What do you do?", "options": ["Fill it in with anything", "Stop and report the task", "Ask the client for the password"]}, "answer": 1},
        {"payload": {"question": "The task asks for a screenshot as proof. What should the screenshot show?", "options": ["Your whole desktop", "The confirmation page after you finished, with the details visible", "The task instructions"]}, "answer": 1},
        {"payload": {"question": "You could not finish the task because the website is down. What do you do?", "options": ["Submit a made-up confirmation", "Write what happened as your proof and submit it", "Wait for the deadline and do nothing"]}, "answer": 1},
    ],
    "answer": [
        {"payload": {"question": "What is 7 times 8?"}, "answer": "56"},
        {"payload": {"question": "Which month comes after March?"}, "answer": "april"},
        {"payload": {"question": "How many days are in a week?"}, "answer": "7"},
    ],
}


def samples_for(kind: str) -> list[dict]:
    if kind not in SAMPLES:
        raise ValueError("unknown type")
    shown = "choose" if kind == "do" else kind  # the action-task qualification is a short quiz
    return [{"index": i, "type": shown, "payload": s["payload"]} for i, s in enumerate(SAMPLES[kind])]


EXPLAIN: dict[str, list[str]] = {
    "verify": ["The text says \"Total: $12.40\", so the answer is yes.", "A thank-you message has no amount in it.", "\"Shipped\" says nothing about when it will arrive."],
    "choose": ["\"Receive\" is the correct spelling; \"recieve\" is not.", "\"Short title\" is clearly shorter.", "An apple is a fruit; carrots and potatoes are vegetables."],
    "rate": ["Random letters cannot be read at all: 1.", "A complete, correct sentence: 5.", "Readable but full of mistakes: around 2."],
    "read": ["Type exactly what is written, including the numbers.", "Keep the gate and the time as written.", "Short and exact: Lot 7 Row 3."],
    "label": ["A dead battery and no reply is a complaint.", "\"Does this come in blue?\" is a question.", "\"Best purchase this year\" is praise."],
    "answer": ["7 times 8 is 56.", "April follows March.", "A week has 7 days."],
    "do": ["Never fill in or ask for someone's password; stop and report.", "A screenshot should show the finished result with the details visible.", "If something blocks you, say what happened in your proof."],
}


def score(kind: str, answers: list[Any]) -> tuple[int, bool]:
    results = results_for(kind, answers)
    correct = sum(results)
    return correct, correct >= 2


def results_for(kind: str, answers: list[Any]) -> list[bool]:
    samples = SAMPLES[kind]
    out = []
    for sample, given in zip(samples, answers, strict=False):
        if kind == "rate":
            try:
                out.append(abs(float(given) - float(sample["answer"])) <= sample.get("tolerance", 0))
            except (TypeError, ValueError):
                out.append(False)
        else:
            out.append(_norm(given) == _norm(sample["answer"]))
    while len(out) < len(samples):
        out.append(False)
    return out
