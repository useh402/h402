"""Work that is answered by typing, not by pointing a camera: calls to make and write up, questions to ask at a counter,
pages to open as a person and read out, forms to fill and report on, things only a local knows, judgements only people
can make, and text in the physical world to copy out exactly.

Every task here is a `do` task with written proof, or a short judgement task (`choose`, `rate`, `label`, `verify`) with
text to judge. None of them can be finished with a photo alone. United States only.
"""

from __future__ import annotations


def _do(cat: str, title: str, instructions: str, minutes: int, location: str = "Remote", url: str | None = None, acceptance: str = "", difficulty: str = "medium") -> dict:
    payload: dict = {"category": cat, "instructions": instructions, "proof": "text"}
    if url:
        payload["url"] = url
    return {"type": "do", "title": title, "location": location, "effortMinutes": minutes, "difficulty": difficulty, "acceptance": acceptance or "Specific, first-hand, and complete for what was asked, in your own words", "payload": payload, "timeLimitSeconds": 1800}


def _choose(cat: str, title: str, question: str, options: list[str]) -> dict:
    return {"type": "choose", "title": title, "location": "Remote", "effortMinutes": 1, "difficulty": "easy", "workers": 3, "payload": {"category": cat, "question": question, "options": options}}


def _rate(cat: str, title: str, item: str, rubric: str) -> dict:
    return {"type": "rate", "title": title, "location": "Remote", "effortMinutes": 1, "difficulty": "easy", "workers": 3, "payload": {"category": cat, "item": item, "rubric": rubric}}


def _label(cat: str, title: str, item: str, labels: list[str]) -> dict:
    return {"type": "label", "title": title, "location": "Remote", "effortMinutes": 1, "difficulty": "easy", "workers": 3, "payload": {"category": cat, "item": item, "labels": labels}}


def _verify(cat: str, title: str, text: str, question: str) -> dict:
    return {"type": "verify", "title": title, "location": "Remote", "effortMinutes": 1, "difficulty": "easy", "workers": 3, "payload": {"category": cat, "text": text, "question": question}}


# Calls: who answered, what they said, when. Nothing to photograph; everything to write down.
CALLS = [
    _do("calls", "Call a plumber in Atlanta and ask the call-out fee for a weekday leak", "Call any plumbing company in Atlanta, GA during business hours. Say you are asking for information. Ask the fee just to come out on a weekday for a leaking kitchen tap, and whether that fee is waived if you go ahead with the repair. Write the company, the number, the time, the person's first name, and both answers in their words.", 10),
    _do("calls", "Call a daycare in Minneapolis and ask the weekly rate for a toddler", "Call any licensed daycare centre in Minneapolis, MN. Ask the weekly full-time rate for a two-year-old, whether there is a waitlist, and how long it is. Write the centre, the number, the time, who answered, and the answers exactly.", 12),
    _do("calls", "Call a car dealership in Houston and ask the out-the-door price of an oil change", "Call the service department of any car dealership in Houston, TX. Ask the total price of a synthetic oil change for a 2019 Toyota Camry including tax and shop fees, and the earliest appointment. Write the dealership, the number, the time, who answered, the price, and the date offered.", 10),
    _do("calls", "Call an urgent care in Seattle and ask the self-pay price of a visit", "Call any urgent care clinic in Seattle, WA. Ask the self-pay price for a basic visit without insurance and whether an X-ray costs extra. Write the clinic, the number, the time, who answered, and the figures they gave.", 10),
    _do("calls", "Call a moving company in Denver and ask the hourly rate for two movers and a truck", "Call any licensed moving company in Denver, CO. Ask the hourly rate for two movers and a truck on a Saturday, the minimum hours, and whether there is a travel fee. Write the company, the number, the time, who answered, and the answers.", 12),
    _do("calls", "Call a dog groomer in Phoenix and ask the price for a medium dog", "Call any dog grooming salon in Phoenix, AZ. Ask the price of a full groom for a 40-pound mixed-breed dog and the next available slot. Write the salon, the number, the time, who answered, the price, and the date offered.", 8),
    _do("calls", "Call a notary in Tampa and ask whether they travel and what they charge", "Call any notary public listed in Tampa, FL. Ask whether they do mobile visits, the fee per signature, and the travel fee. Write the name or business, the number, the time, and the answers.", 8),
    _do("calls", "Call a community college in Chicago and ask the per-credit tuition for residents", "Call the admissions line of any City Colleges of Chicago campus in Chicago, IL. Ask the current per-credit-hour tuition for Illinois residents and whether there is a registration fee. Write the campus, the number, the time, who answered, and the figures.", 12),
    _do("calls", "Call a bike shop in Portland and ask whether they rent bikes by the day", "Call any bike shop in Portland, OR. Ask whether they rent bikes, the price for one day, and what deposit or ID they need. Write the shop, the number, the time, who answered, and the answers.", 8),
    _do("calls", "Call a pet-friendly hotel in Nashville and ask the real pet fee", "Call the front desk of any hotel in Nashville, TN that says it allows pets. Ask the pet fee per night or per stay, the weight limit, and whether the fee is refundable. Write the hotel, the number, the time, who answered, and the answers word for word.", 10),
    _do("calls", "Call a tax office in Detroit and ask what documents a first-time filer needs", "Call any tax-preparation office in Detroit, MI. Ask what documents a first-time filer with one W-2 should bring and the price of a basic return. Write the office, the number, the time, who answered, and the list they gave.", 12),
    _do("calls", "Call a gym in Philadelphia and ask what it really costs to cancel", "Call any gym in Philadelphia, PA. Ask the monthly price, the sign-up fee, the notice period to cancel, and whether cancelling needs to be done in person. Write the gym, the number, the time, who answered, and every answer.", 10),
]

# Ask at the counter: the answer comes from a person behind it, and you write it down.
ASK = [
    _do("business_research", "Ask a pharmacy near you the cash price of a common generic", "Go to any pharmacy counter near you and ask the cash price, without insurance, of a 30-day supply of generic atorvastatin 20 mg. Do not buy anything. Write the pharmacy, the city, the time, the price, and whether they mentioned a discount card.", 20),
    _do("business_research", "Ask a bakery near you what time today's bread is baked and when it sells out", "Go to any independent bakery near you. Ask what time the bread comes out of the oven and when it usually sells out. Write the bakery, the city, the time you asked, and the answer in their words.", 15),
    _do("business_research", "Ask a mechanic near you the price of a brake pad replacement", "Walk into any independent auto repair shop near you. Ask the price to replace front brake pads on a 2017 Honda CR-V, parts and labour, and how long it takes. Write the shop, the city, the time, who you spoke to, and the quote.", 20),
    _do("business_research", "Ask a farmers market stall what they charge for a dozen eggs and where the farm is", "At any farmers market near you, ask one egg seller the price per dozen and where the farm is. Write the market, the city, the stall name, the price, and the farm's town.", 15),
    _do("business_research", "Ask a phone repair shop near you the price of an iPhone screen replacement", "Go to any phone repair shop near you. Ask the price to replace the screen on an iPhone 13, whether the part is original, and the wait time. Write the shop, the city, the time, and the answers.", 15),
    _do("business_research", "Ask a post office counter near you the cheapest way to send a 2-pound box across the country", "At a USPS counter near you, ask the cheapest way to send a 2-pound box from your ZIP to Los Angeles, CA and how many days it takes. Write the office, your city, the time, the service they named, the price, and the days.", 15),
    _do("community_resources", "Ask a public library near you what you need to get a card today", "Go to any public library branch near you and ask what documents are needed to get a library card today, and whether non-residents can get one. Write the branch, the city, the time, who answered, and the answer.", 15),
    _do("community_resources", "Ask a food pantry near you who can come and what to bring", "Go to a food pantry near you during its hours. Ask who is eligible, whether an ID or proof of address is needed, and how often a person can come. Write the pantry, the city, the hours they told you, and the answers.", 20),
    _do("accessibility", "Ask a cinema near you about wheelchair seating and captioning devices", "Go to or call any cinema near you. Ask where the wheelchair spaces are, whether a companion seat is next to them, and whether captioning devices are available. Write the cinema, the city, who answered, and the answers.", 15),
    _do("accessibility", "Ask a restaurant near you whether the restroom is accessible and how to reach it", "At any sit-down restaurant near you, ask whether the restroom is wheelchair accessible and whether there are steps anywhere between the door and the table. Write the restaurant, the city, the time, who answered, and what they said.", 12),
]

# Pages and apps that refuse scripts: open them as a normal visitor and write out what they show.
BLOCKED = [
    _do("blocked_sites", "Open Instacart for your ZIP and write the price of a dozen large eggs at three stores", "Open Instacart for your own ZIP code and look up a dozen large grade A eggs at three different stores. Write your ZIP, the three stores, each price, and whether each was marked as in stock.", 10, url="https://www.instacart.com/"),
    _do("blocked_sites", "Open the Uber app and write the fare estimates from your home to the nearest airport", "Open the Uber app at home and set the destination to the nearest airport. Write your city, the airport, the time, and the estimated fare for UberX, Comfort and XL. Do not book.", 5),
    _do("blocked_sites", "Open Ticketmaster and write the full fee breakdown for the cheapest ticket to any concert", "Open Ticketmaster, pick any concert in the United States, and go as far as the checkout page for the cheapest ticket without buying. Write the event, the venue, the date, the face price, the service fee, the order fee, and the total.", 10, url="https://www.ticketmaster.com/"),
    _do("blocked_sites", "Open Zillow and write the three newest rentals under $1,800 in your city", "Open Zillow, search rentals in your city, filter under $1,800 a month, sort newest. Write your city, and for each of the three newest: the street name (no number), the rent, bedrooms, and the posting date.", 10, url="https://www.zillow.com/"),
    _do("blocked_sites", "Open the DoorDash app and write every fee on a small order from a restaurant near you", "Open the DoorDash app, pick any restaurant near you, add one item and go to checkout without paying. Write your city, the restaurant, the item price, the delivery fee, the service fee, any small-order fee, and the suggested tip shown.", 8),
    _do("blocked_sites", "Open the Amtrak site and write the fares for tomorrow from Chicago to Milwaukee", "Open Amtrak and search tomorrow's trains from Chicago, IL to Milwaukee, WI. Do not log in or book. Write the date, every departure time, and the lowest fare for each departure.", 8, url="https://www.amtrak.com/"),
    _do("blocked_sites", "Open OpenTable and write the earliest table for two tonight at three restaurants in your city", "Open OpenTable for your city tonight for two people. Write your city and, for three restaurants, the name and the earliest time offered, or 'none' if nothing is available. Do not book.", 8, url="https://www.opentable.com/"),
    _do("blocked_sites", "Open the Walmart app and write the price of the same five items for pickup at two stores", "Open the Walmart app and choose a store near you. Note the prices of a gallon of whole milk, a dozen eggs, a loaf of white bread, bananas per pound, and a 2-liter cola. Switch to a second store and note them again. Write your city, both stores, and the ten prices.", 12),
    _do("blocked_sites", "Open Airbnb and write the full price breakdown for a weekend in your city", "Open Airbnb, search your city for next Friday to Sunday for two guests, and open any listing. Write your city, the listing's nightly price, the cleaning fee, the service fee, taxes, and the total shown.", 8, url="https://www.airbnb.com/"),
    _do("blocked_sites", "Open your bank's app and write the fees page for a checking account", "Signed into your own bank's app, open the fee schedule for a basic checking account. Write the bank, the monthly fee, how it is waived, the overdraft fee, and the out-of-network ATM fee. Do not share any account details.", 8),
]

# Forms and listings: do the thing, then write what happened.
FORMS = [
    _do("forms_and_listings", "Submit a contact form on any US dentist's website and write how long until a reply", "Find a dentist in the United States with a contact form. Ask whether they take new patients. Write the practice, the city, the time you sent it, and the time and content of the reply, or 'no reply' after 24 hours.", 15),
    _do("forms_and_listings", "Request a quote from a car insurer online and write every question it asks before the price", "Start a quote on any US car insurer's website and stop before giving your real contact details. Write the insurer, each piece of information it asked for in order, and the point where it refused to continue without a phone number or email.", 15),
    _do("forms_and_listings", "Sign up for a store newsletter and write when the first email arrives and what it offers", "Sign up for any US retailer's email newsletter with an address you control. Write the retailer, the time you signed up, the time the first email arrived, its subject line, and the offer it contained.", 10),
    _do("forms_and_listings", "Report a streetlight outage on your city's 311 site and write the ticket number and the promised time", "Open your city's 311 or service request site and report a real streetlight outage near you. Write the city, the address you reported, the ticket or reference number, and the response time the site promised.", 12),
    _do("forms_and_listings", "Book a free library study room online and write how far ahead you could book", "Open your public library's room-booking page. Write the library, the city, the earliest slot available today, the furthest date it let you book, and the maximum hours per booking. Cancel the booking if you made one.", 10),
    _do("forms_and_listings", "Message a Facebook Marketplace seller in your city and write how long they took to answer", "On Facebook Marketplace in your city, message the seller of any item under $50 asking if it is still available. Write your city, the item, the time you sent it, the time they replied, and what they said.", 20),
]

# Local knowledge: things people who live there know. Written from experience, with the detail that proves it.
LOCAL = [
    _do("local_knowledge", "Which Chicago L stations have no elevator on the Blue Line? Write them from experience", "Only if you ride it: list the Blue Line stations you know have no elevator or where the elevator is often out, and the last time you saw each. Write the stations and the dates.", 10, location="Chicago, IL"),
    _do("local_knowledge", "Where is street parking actually possible near Dodger Stadium on game night?", "Only if you live in Los Angeles: write the streets where you have found free or cheap parking within a 20-minute walk of Dodger Stadium on a game night, how early you had to arrive, and the time you did it last.", 10, location="Los Angeles, CA"),
    _do("local_knowledge", "What does the I-35 commute into downtown Austin really take at 8 am?", "Only if you drive it: write where you get on I-35, where you get off, the time you leave, and how long it took on your last three weekday mornings.", 8, location="Austin, TX"),
    _do("local_knowledge", "Which Brooklyn neighbourhoods have the most reliable G train service in your experience?", "Only if you ride the G: write which stops you use, how long you usually wait at rush hour and late evening, and the last time you were stranded by a service change.", 8, location="New York, NY"),
    _do("local_knowledge", "Where can you still find a free public restroom in downtown San Francisco?", "Only if you know the area: write three places in downtown San Francisco with a public restroom that does not require a purchase, the hours you have found them open, and the last time you used each.", 8, location="San Francisco, CA"),
    _do("local_knowledge", "Which Denver neighbourhoods lose power most in snowstorms, from your experience?", "Only if you live in Denver: write your neighbourhood, how many times your power went out in the last two winters, how long each outage lasted, and what your neighbours say about theirs.", 8, location="Denver, CO"),
    _do("local_knowledge", "What is the real wait for a MARTA train at Five Points on a weekday evening?", "Only if you ride MARTA: write the line, the time you usually travel, how long you waited on your last three trips through Five Points, and whether the station board was accurate.", 8, location="Atlanta, GA"),
    _do("local_knowledge", "Which Seattle neighbourhoods are walkable at night and which are not, from living there?", "Only if you live in Seattle: write the neighbourhoods you walk in after 10 pm and feel fine, the ones you avoid, and one concrete reason for each from your own experience.", 10, location="Seattle, WA"),
    _do("local_knowledge", "Where do Portland locals go for a cheap weekday lunch under $12?", "Only if you live in Portland: write three places where you have eaten lunch for under $12 in the last month, what you had, the price, and the neighbourhood.", 8, location="Portland, OR"),
    _do("local_knowledge", "What do Miami drivers pay for parking near South Beach on a Saturday night?", "Only if you have done it recently: write where you parked near South Beach on a Saturday night, what it cost, how long it took to find, and the date.", 8, location="Miami, FL"),
    _do("local_knowledge", "Which Boston T stops flood or close in heavy rain, from experience?", "Only if you ride the T: write the stops you have seen closed or flooded in heavy rain, which line, when, and how you got around it.", 8, location="Boston, MA"),
    _do("local_knowledge", "What does a Philadelphia row-house actually pay for heat in January?", "Only if you live in a Philadelphia row house: write the rough square footage, the fuel (gas, oil, electric), what you paid in January, and the thermostat setting you kept.", 8, location="Philadelphia, PA"),
]

# Text in the physical world: copy it out exactly. Only someone holding the thing can do it.
TRANSCRIBE = [
    _do("documents_and_receipts", "Type the full warning label on a cleaning product in your home", "Take any household cleaning product you own. Type the product name and the complete warning or caution text on the back label, word for word, with the line breaks as they appear.", 10, acceptance="The exact text of the label; spelling and punctuation as printed"),
    _do("documents_and_receipts", "Type every line of a grocery receipt from this week, with the totals", "Take a grocery receipt from this week. Type the store, the date, every line item with its price, the subtotal, the tax, and the total, exactly as printed. Leave out any card number.", 10, acceptance="Every line item and the totals, as printed"),
    _do("documents_and_receipts", "Type the terms printed on the back of a parking ticket stub or receipt", "Take any parking stub or receipt you have. Type the garage or lot name, the city, and the full terms printed on it, word for word.", 8, acceptance="The exact text, as printed"),
    _do("documents_and_receipts", "Type the exact wording of a sign posted in your building's lobby or hallway", "Find any notice posted in your apartment building, office or dormitory. Type the full text exactly as written, and say where it is posted and the date on it if any. Do not include anyone's name or unit number.", 8, acceptance="The exact text of the notice"),
    _do("documents_and_receipts", "Type the ingredients list of a packaged food you have, in order", "Take any packaged food in your kitchen. Type the product name and the full ingredients list in the exact order and spelling on the package, including the allergen statement.", 8, acceptance="Every ingredient in order, as printed"),
    _do("documents_and_receipts", "Type the fine print on a coupon or flyer you received in the mail this week", "Take any coupon or flyer that came in your mail this week. Type the business, the offer, the expiry date, and every line of the fine print exactly as printed.", 8, acceptance="The offer and the complete fine print, as printed"),
]

# Judgement: no formula, only people. Typed text to judge; three people decide.
JUDGEMENT = [
    _choose("judgement", "Which reply to an angry customer sounds more sincere?", "A customer wrote: 'My order arrived broken and nobody answers the phone.' Which reply sounds more sincere?", ["We're sorry to hear that. Please reply with your order number and a photo of the damage and we'll send a replacement today.", "We apologise for any inconvenience this may have caused. Our team is committed to excellence. Please contact support for further assistance."]),
    _choose("judgement", "Which subject line would you open first?", "Which of these subject lines would you open first in a crowded inbox?", ["Your receipt from Saturday", "Quick question about Saturday", "Action required: Saturday"]),
    _choose("judgement", "Which product name sounds more trustworthy for a baby monitor?", "Which name would you trust more on a baby monitor box?", ["NestWatch", "BabyGuard Pro Max", "Lull"]),
    _choose("judgement", "Which out-of-office message sounds more professional?", "Which out-of-office message would you rather receive from a lawyer?", ["I'm out until Monday 14th and will reply then. For anything urgent, call the office at the number below.", "Hey! I'm away living my best life until the 14th. Will get back to you after!", "This mailbox is unattended. Your message will be processed in due course."]),
    _choose("judgement", "Which apology from a landlord sounds like it means it?", "A landlord took nine days to fix the heating. Which message sounds like a real apology?", ["I'm sorry it took nine days. That's too long, and I've taken $150 off next month's rent.", "Sorry for the delay, these things happen. Let me know if there's anything else.", "The heating has been fixed. Thank you for your patience."]),
    _rate("judgement", "Rate how clear this parking sign is", "Sign text: 'NO PARKING 8AM-10AM MON WED FRI STREET CLEANING. 2 HOUR PARKING 10AM-6PM EXCEPT SUNDAY. PERMIT ZONE C EXEMPT.'", "5 means a visitor would know at once whether they can park now; 1 means it would take minutes and a guess"),
    _rate("judgement", "Rate how polite this message to a neighbour is", "Message: 'Hi, your dog has been barking most of the night this week. I know it's not on purpose, but I work early. Could you look into it? Thanks.'", "5 means polite and reasonable; 1 means rude or threatening"),
    _rate("judgement", "Rate how easy this recipe step is to follow", "Step: 'Fold the egg whites into the batter in three additions, cutting down the middle and sweeping up the side, until no streaks remain but the mixture is still airy.'", "5 means a first-time cook could do it from this text alone; 1 means they could not"),
    _rate("judgement", "Rate how misleading this ad line is", "Ad line: 'Up to 70% off everything!' when the store's sale page shows 10% off most items and 70% off one clearance rack", "5 means clearly misleading; 1 means fair"),
    _label("sorting_and_tagging", "Tag this customer message", "Message: 'I ordered the blue one and got the green one. Honestly the green looks fine, but I'd like to know if I can swap it without paying shipping again.'", ["complaint", "question", "praise", "return request", "spam"]),
    _label("sorting_and_tagging", "Tag this review", "Review: 'Amazing product!!! Changed my life!!! Click here for 50% off: bit.ly/xyz123'", ["genuine", "spam", "promotional", "off topic"]),
    _label("sorting_and_tagging", "Tag this support ticket", "Ticket: 'The app crashes every time I open the camera on my Pixel 8. Started after yesterday's update. I've reinstalled twice.'", ["bug", "feature request", "billing", "account access", "how-to question"]),
    _verify("judgement", "Would a reasonable person read this as a threat?", "Text message: 'You'll regret parking in my spot again. Next time I won't be so nice.'", "Would a reasonable person read this message as a threat?"),
    _verify("judgement", "Is this listing description honest about the apartment's size?", "Listing: 'Spacious studio, 310 sq ft, with a cozy sleeping nook and efficient kitchenette.'", "Is 'spacious' an honest word for a 310 square foot studio?"),
    _verify("judgement", "Does this reply answer the question that was asked?", "Question: 'Do you deliver to ZIP 60614 on Sundays?' Reply: 'We deliver across Chicagoland seven days a week! Order now and get 10% off.'", "Does the reply actually answer whether they deliver to 60614 on Sundays?"),
]


def manual_tasks() -> list[dict]:
    return CALLS + ASK + BLOCKED + FORMS + LOCAL + TRANSCRIBE + JUDGEMENT
