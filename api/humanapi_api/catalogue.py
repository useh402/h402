"""The real-world task catalogue: categories, what a client needs, and how it maps to a task type.

A client's software hits something only a person can settle. Each category below is one of those
situations, with concrete examples. The catalogue drives the feed grouping, the category labels on
cards, and the starter tasks for a new marketplace.
"""

from __future__ import annotations

CATEGORIES: dict[str, dict] = {
    "calls": {
        "label": "Phone calls",
        "need": "Someone has to call and ask. Businesses answer people, not programs.",
        "examples": ["Call this clinic and ask if they take walk-ins today. Write what they said.", "Call the restaurant and ask whether a table for six is possible on Saturday at 8.", "Call this store and ask if the item in the link is in stock."],
    },
    "go_and_see": {
        "label": "Go and see",
        "need": "The answer is in the physical world: a shelf, a line, a price board, a closed sign.",
        "examples": ["Go to this store and photograph the price tag for the item.", "Is this ATM working right now? Photo of the screen.", "Is this restaurant open at 11 am, or is the sign flipped to closed?"],
    },
    "blocked_sites": {
        "label": "Sites that block automation",
        "need": "The page or app refuses automated visitors. A person browsing normally is allowed.",
        "examples": ["Open the app, search for this item and send a screenshot of the price.", "Check whether a delivery slot is available for this ZIP code tomorrow.", "Open the booking page and tell us the earliest available date."],
    },
    "forms_and_listings": {
        "label": "Forms and listings",
        "need": "Fill in a public form, confirm a listing is live, check a booking page.",
        "examples": ["Fill in this public enquiry form with the details given and send a screenshot of the confirmation.", "Is this apartment listing still available? Open it and tell us.", "Does this event page still show tickets on sale?"],
    },
    "real_and_current": {
        "label": "Is it real, is it current",
        "need": "Online data lags reality. Only a fresh look settles it.",
        "examples": ["Does this business exist at this address? Check the map and the latest reviews.", "Is this review genuine or does it look paid for?", "Is this photo recent, or an old stock image?"],
    },
    "documents_and_receipts": {
        "label": "Documents and receipts",
        "need": "Read what a photo says, check a total, confirm a document is complete.",
        "examples": ["Type the total and the date from this receipt.", "Does this invoice show sales tax as a separate line?", "Read the handwritten note in this photo."],
    },
    "judgement": {
        "label": "Human judgement",
        "need": "Taste, tone, what looks trustworthy, what reads as rude. There is no formula, only people.",
        "examples": ["Which of these two messages sounds more polite to a customer?", "Which product photo would you click on?", "Does this ad come across as misleading?"],
    },
    "local_knowledge": {
        "label": "Local knowledge",
        "need": "Things only someone who lives there knows.",
        "examples": ["Is I-405 usually jammed northbound at 5 pm on weekdays?", "Is this neighborhood fine to walk at night?", "Which subway exit is closest to this building?"],
    },
    "community_resources": {
        "label": "Community resources",
        "need": "Find and verify public services for a city: pantries, libraries, cooling centers, drop-off sites.",
        "examples": ["Find three food pantries in Phoenix with published hours and eligibility.", "Verify weekend hours for five Chicago library branches.", "Find official cooling centers in Las Vegas and their hours."],
    },
    "accessibility": {
        "label": "Accessibility and local services",
        "need": "Is a place actually accessible, what are the fare options, where are the step-free entrances.",
        "examples": ["Compare a venue's published accessible entrance with what you can confirm.", "Find venues with assistive listening systems in San Francisco.", "Collect official accessible voting information for Milwaukee."],
    },
    "business_research": {
        "label": "Small business and consumer research",
        "need": "Compare prices, find providers, check grant deadlines, verify a market schedule.",
        "examples": ["Compare a grocery basket across Dallas retailers.", "Collect coworking day-pass prices in Miami.", "Find currently open small-business grants in Cleveland."],
    },
    "research_and_verification": {
        "label": "Research and verification",
        "need": "Does the source really say that; where did this quote come from; which claims lack evidence.",
        "examples": ["Check a company claim against primary sources.", "Trace a quotation to its original publication.", "Flag unsupported statements in a report."],
    },
    "technical": {
        "label": "Technical checks",
        "need": "Reproduce an error, test a page on mobile, verify a setup guide, check an example still works.",
        "examples": ["Follow these steps in a test environment and capture the exact error.", "Complete this flow on a mobile browser and report layout issues.", "Run this test suite and isolate the failing case."],
    },
    "web3": {
        "label": "Blockchain checks",
        "need": "Explain a failed transaction, verify an address against official sources, check a bridge completed.",
        "examples": ["Explain why this transaction failed, in plain English, with explorer evidence.", "Does this token address match the project's official links?", "Trace this bridge transaction through each stage."],
    },
    "sorting_and_tagging": {
        "label": "Sorting and tagging",
        "need": "Put things in the right bucket when the rules are fuzzy: complaint or praise, spam or real.",
        "examples": ["Is this customer message a complaint, a question or praise?", "Is this review genuine or spam?", "Which category does this product belong to?"],
    },
}

# Starter tasks: genuine, public, doable work used when the marketplace is new or quiet. United States only.
STARTER_TASKS: list[dict] = [
    {"title": "Call a Walgreens in San Francisco and ask about pharmacy hours", "type": "do", "payload": {"category": "calls", "instructions": "Call the Walgreens at 1201 Market St, San Francisco, CA on (415) 362-6363 during store hours. Say you are calling to ask a question. Ask: do they have blood pressure monitors in stock, and what time does the pharmacy counter close today? Write who answered (just 'a staff member' is fine), what they said, and the time you called.", "proof": "text"}, "pricePerWorker": 1_500_000, "timeLimitSeconds": 1800},
    {"title": "Call Katz's Delicatessen in New York and ask about group reservations", "type": "do", "payload": {"category": "calls", "instructions": "Call Katz's Delicatessen, 205 E Houston St, New York, NY on (212) 254-2246. Ask whether they take reservations for a group of six on Saturday evening, and if yes, how. Write exactly what they told you and the time of the call.", "proof": "text"}, "pricePerWorker": 1_500_000, "timeLimitSeconds": 1800},
    {"title": "Photograph the milk price tag at a Jewel-Osco in Chicago", "type": "do", "payload": {"category": "go_and_see", "instructions": "If you are in Chicago: go to any Jewel-Osco and photograph the shelf price tag for a gallon of whole milk (store brand). Write the store location and the price. The tag must be readable in the photo.", "proof": "both"}, "pricePerWorker": 3_000_000, "timeLimitSeconds": 1800},
    {"title": "Check whether the Chase ATM at 6th and Congress in Austin is working", "type": "do", "payload": {"category": "go_and_see", "instructions": "If you are in Austin: go to the Chase ATM closest to 6th Street and Congress Avenue. Is it working right now? Take a photo of the ATM screen (not of your card or any receipt) and write whether it is in service or showing an error.", "proof": "both"}, "pricePerWorker": 3_000_000, "timeLimitSeconds": 1800},
    {"title": "Check the price of Kerrygold butter on Instacart for ZIP 94103", "type": "do", "payload": {"category": "blocked_sites", "instructions": "Open the Instacart website for ZIP code 94103 and pick Safeway. Search for 'Kerrygold butter 8 oz'. Write the price shown and whether it is available for delivery today. Add a screenshot of the product with the price visible.", "url": "https://www.instacart.com/", "proof": "both"}, "pricePerWorker": 1_200_000},
    {"title": "Find the earliest Amtrak Boston to New York departure on Friday and its fare", "type": "do", "payload": {"category": "blocked_sites", "instructions": "Open the Amtrak site and check the earliest Northeast Regional departure from Boston South Station to New York Penn Station this coming Friday morning, and the lowest coach fare shown. Do not log in and do not book. Write what you see and add a screenshot.", "url": "https://www.amtrak.com/", "proof": "both"}, "pricePerWorker": 1_500_000},
    {"title": "Is the newest apartment listing on Austin Craigslist still available?", "type": "do", "payload": {"category": "forms_and_listings", "instructions": "Open the Austin, Texas apartments page and open the newest listing. Is it still available? Write the monthly rent shown and the date it was posted or last updated. Add a screenshot of the listing.", "url": "https://www.craigslist.org/search/area/austin?cat=apa", "proof": "both"}, "pricePerWorker": 1_000_000},
    {"title": "Does Blue Bottle Coffee at 66 Mint St, San Francisco still exist?", "type": "do", "payload": {"category": "real_and_current", "instructions": "Search Google Maps for 'Blue Bottle Coffee, 66 Mint St, San Francisco'. Does it still exist there? Open the latest three reviews and write their dates. Say whether the listing shows 'Permanently closed'.", "url": "https://www.google.com/maps/search/Blue+Bottle+Coffee+66+Mint+St+San+Francisco", "proof": "text"}, "pricePerWorker": 1_000_000},
    {"title": "Is the total on this receipt readable?", "type": "verify", "payload": {"category": "documents_and_receipts", "image": "https://images.unsplash.com/photo-1554224155-6726b3ff858f?w=1200", "question": "Is the total amount on this receipt readable?"}},
    {"title": "Type the text in this photo exactly as written", "type": "read", "payload": {"category": "documents_and_receipts", "image": "https://images.unsplash.com/photo-1586281380349-632531db7ed4?w=1200"}},
    {"title": "Type the text in this document photo exactly as written", "type": "read", "payload": {"category": "documents_and_receipts", "image": "https://images.unsplash.com/photo-1554224154-26032ffc0d07?w=1200"}},
    {"title": "Which of these three bag photos would you click on first?", "type": "choose", "payload": {"category": "judgement", "question": "Which photo would you click on first if you were buying this bag?", "options": ["https://images.unsplash.com/photo-1548036328-c9fa89d128fa?w=800", "https://images.unsplash.com/photo-1590874103328-eac38a683ce7?w=800", "https://images.unsplash.com/photo-1553062407-98eeb64c6a62?w=800"]}},
]


def category_of(payload: dict) -> str | None:
    c = payload.get("category") if isinstance(payload, dict) else None
    return c if c in CATEGORIES else None


def catalogue_view() -> dict:
    return {key: {"label": v["label"], "need": v["need"], "examples": v["examples"]} for key, v in CATEGORIES.items()}
