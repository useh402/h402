"""Tasks that need a photo taken now. The answer is not in the task: someone has to be there with a camera.

Each is a `do` task with `proof: "photos"`. Go-and-see tasks carry the place's coordinates; the photo must be taken
within a few hundred metres of it. Every photo must show the capture code the worker is given when they take the task.

A photo alone is never the whole answer: every task names what the person has to type as well (`write`), and the operator
looks at the pictures and the text before anyone is paid.
"""

from __future__ import annotations

CODE_RULE = " Write the capture code shown on your task on a piece of paper and keep it in every shot."

# (title, city, state, lat, lng, what to photograph, minutes)
PLACES = [
    ("Photograph the posted hours at the main entrance of the Austin Central Library", "Austin", "TX", 30.2655, -97.7527, "the hours sign at the main entrance on West Cesar Chavez Street, close enough to read", 35),
    ("Photograph the departures board inside Chicago Union Station right now", "Chicago", "IL", 41.8787, -87.6403, "the main departures board in the Great Hall or concourse, with the current times readable", 35),
    ("Photograph a price sign at a produce stall in Pike Place Market", "Seattle", "WA", 47.6097, -122.3422, "one produce stall's handwritten or printed price sign, with the stall visible", 40),
    ("Photograph the main concourse clock at Grand Central Terminal", "New York", "NY", 40.7527, -73.9772, "the four-faced clock above the information booth, with the time readable", 30),
    ("Photograph the posted hours at the Ferry Building's main doors in San Francisco", "San Francisco", "CA", 37.7955, -122.3937, "the hours sign at the Embarcadero entrance, close enough to read", 35),
    ("Photograph the posted hours at Faneuil Hall Marketplace in Boston", "Boston", "MA", 42.3601, -71.0547, "any posted hours sign at a main entrance of the marketplace, readable", 35),
    ("Photograph the ticket counter and its posted hours at Denver Union Station", "Denver", "CO", 39.7530, -105.0000, "the Amtrak ticket counter area and the hours sign next to it", 35),
    ("Photograph the current line at the Santa Monica Pier entrance", "Los Angeles", "CA", 34.0094, -118.4973, "the entrance area from the street side, showing how many people are waiting or walking in", 30),
    ("Photograph the posted hours at the Alamo's main gate in San Antonio", "San Antonio", "TX", 29.4259, -98.4861, "the visitor hours sign at the entrance on Alamo Plaza", 35),
    ("Photograph the notice board at Pioneer Courthouse Square in Portland", "Portland", "OR", 45.5189, -122.6793, "the public notice or events board on the square, with any posted notices readable", 30),
    ("Photograph a restaurant menu board on Lincoln Road in Miami Beach", "Miami Beach", "FL", 25.7906, -80.1370, "one restaurant's outdoor menu board with prices readable, and the restaurant name visible", 35),
    ("Photograph the posted hours at the Lincoln Park Zoo east gate in Chicago", "Chicago", "IL", 41.9211, -87.6340, "the hours sign at the east gate on Cannon Drive, readable", 35),
]

# From home: things only someone holding the object can show. (title, category, what to photograph, minutes, note)
AT_HOME = [
    ("Photograph the nutrition label of a cereal box you have at home", "documents_and_receipts", "the full nutrition facts panel of any breakfast cereal box, flat and readable, with the brand name in the shot", 8),
    ("Photograph the rate line on your most recent electric bill", "documents_and_receipts", "the part of a US electric bill that shows the price per kWh and the billing period. Cover your name, address and account number with your hand or paper", 10),
    ("Photograph the model label on the back or bottom of your router", "technical", "the sticker with the model number on your home router, readable; cover any login details printed on it", 8),
    ("Photograph the expiry date on a medicine bottle in your home", "documents_and_receipts", "the expiry or 'use by' date printed on any over-the-counter medicine bottle or box, readable, with the product name visible", 8),
    ("Photograph your car's dashboard with the odometer reading", "real_and_current", "the dashboard of a car with the odometer reading clearly visible. Do not include the licence plate or any documents", 8),
    ("Photograph a delivery app on your phone showing the fee for a nearby order", "blocked_sites", "a food delivery app open to a restaurant checkout screen that shows the delivery fee and service fee for your address. Take the picture with a second camera or a mirror; a screenshot is not accepted", 12),
    ("Photograph the price tag of a gallon of milk at your nearest grocery store", "go_and_see", "the shelf price tag for a gallon of whole milk, store brand if there is one, with the tag readable and the store aisle around it", 25),
    ("Photograph the gas price sign at the station nearest to you", "go_and_see", "the large price sign outside a gas station with the regular price readable, and the station's brand visible", 20),
]


# What the person types next to the photos, by title. The operator reads this against the picture.
WRITE: dict[str, str] = {
    'Photograph the posted hours at the main entrance of the Austin Central Library': 'The hours for each day of the week, as printed on the sign',
    'Photograph the departures board inside Chicago Union Station right now': 'The next three departures on the board: train, destination, time and status',
    'Photograph a price sign at a produce stall in Pike Place Market': 'The stall name and every item and price on the sign',
    'Photograph the main concourse clock at Grand Central Terminal': 'The time on the clock and how busy the concourse was',
    "Photograph the posted hours at the Ferry Building's main doors in San Francisco": 'The hours for each day as printed on the sign',
    'Photograph the posted hours at Faneuil Hall Marketplace in Boston': 'The hours on the sign and which entrance you used',
    'Photograph the ticket counter and its posted hours at Denver Union Station': 'The counter hours as posted and whether it was staffed',
    'Photograph the current line at the Santa Monica Pier entrance': 'Roughly how many people were waiting and the time',
    "Photograph the posted hours at the Alamo's main gate in San Antonio": 'The visitor hours as printed and the admission price if posted',
    'Photograph the notice board at Pioneer Courthouse Square in Portland': 'The title and date of each notice you can read',
    'Photograph a restaurant menu board on Lincoln Road in Miami Beach': 'The restaurant name and three items with their prices',
    'Photograph the posted hours at the Lincoln Park Zoo east gate in Chicago': 'The hours for today as printed and whether the gate was open',
    'Photograph the nutrition label of a cereal box you have at home': 'The brand, the serving size, and the calories, sugar and sodium per serving',
    'Photograph the rate line on your most recent electric bill': 'The utility, the price per kWh, the kWh used and the billing period',
    'Photograph the model label on the back or bottom of your router': 'The make and model number, and who your internet provider is',
    'Photograph the expiry date on a medicine bottle in your home': 'The product name and the expiry date exactly as printed',
    "Photograph your car's dashboard with the odometer reading": 'The odometer reading, and the make, model and year of the car',
    'Photograph a delivery app on your phone showing the fee for a nearby order': 'The app, the restaurant, the delivery fee, the service fee and your city',
    'Photograph the price tag of a gallon of milk at your nearest grocery store': 'The store, the city, the brand and the price on the tag',
    'Photograph the gas price sign at the station nearest to you': 'The station brand, the city, and the regular, mid and premium prices on the sign',
    "Photograph the date on today's newspaper or a piece of mail": 'The date exactly as printed and the name of the paper or the sender',
    'Photograph the weather outside your window right now': 'Your city, the time, and the weather in a few words',
    "Photograph your thermostat's current temperature": 'The temperature shown, the setting, and the thermostat brand',
    "Photograph your car's fuel gauge": 'Roughly how full the tank is and the make and model of the car',
    'Photograph the price on the shelf tag of any item in your fridge': 'The item, the price on the tag and the store it came from',
    "Photograph the signal bars on your phone's lock screen": 'Your carrier, the number of bars, the network type (5G, LTE) and your city',
    'Photograph the keys on your key ring and count them': 'How many keys there are and what each one is for',
    'Photograph the clock on your microwave or oven': 'The time shown and the appliance brand',
    'Photograph the nearest light switch at its height from the floor': 'The height in inches from the floor to the middle of the switch',
    'Photograph the best-before date on any item in your kitchen': 'The product name and the date exactly as printed',
}


def photo_tasks() -> list[dict]:
    out: list[dict] = []
    for title, city, st, lat, lng, what, minutes in PLACES:
        out.append({
            "type": "do", "title": title, "location": f"{city}, {st}", "effortMinutes": minutes, "difficulty": "medium",
            "acceptance": "One to three photos taken at the place now, with the capture code in the shot and the subject readable, and what they show typed out",
            "payload": {"category": "go_and_see", "instructions": f"Go to the place and photograph {what}. Take one to three photos with your phone's camera.{CODE_RULE} Then type what you saw: {WRITE[title].lower()}.", "proof": "photos", "write": WRITE[title], "geo": {"lat": lat, "lng": lng}},
            "timeLimitSeconds": 1800,
        })
    for title, category, what, minutes in AT_HOME:
        out.append({
            "type": "do", "title": title, "location": "Remote", "effortMinutes": minutes, "difficulty": "easy",
            "acceptance": "One to three photos taken now with the capture code in the shot and the subject readable, and what they show typed out",
            "payload": {"category": category, "instructions": f"Photograph {what}. Take one to three photos with your phone's camera, not screenshots.{CODE_RULE} Then type: {WRITE[title].lower()}.", "proof": "photos", "write": WRITE[title]},
            "timeLimitSeconds": 1800,
        })
    return out


# One-dollar quick checks: a single camera photo of something only the person holding the phone can show, plus a line typed about it, one minute each.
DOLLAR = [
    ("documents_and_receipts", "Photograph the date on today's newspaper or a piece of mail", "the date printed on a newspaper or on the postmark of mail you received today"),
    ("real_and_current", "Photograph the weather outside your window right now", "the view out of a window, showing the sky and the weather at this moment"),
    ("technical", "Photograph your thermostat's current temperature", "your home thermostat's display with the current temperature readable"),
    ("real_and_current", "Photograph your car's fuel gauge", "the fuel gauge on your car's dashboard, with the needle or bars readable; keep the licence plate out of the shot"),
    ("documents_and_receipts", "Photograph the price on the shelf tag of any item in your fridge", "the price tag or sticker still on any item in your fridge or pantry, with the price readable"),
    ("technical", "Photograph the signal bars on your phone's lock screen", "your phone's lock screen showing the signal bars and carrier name, taken with a second camera or a mirror"),
    ("sorting_and_tagging", "Photograph the keys on your key ring and count them", "your key ring laid flat so every key is visible; write how many keys it holds"),
    ("real_and_current", "Photograph the clock on your microwave or oven", "the clock display on your microwave or oven with the time readable"),
    ("accessibility", "Photograph the nearest light switch at its height from the floor", "a light switch in your home with a tape measure or ruler showing its height from the floor"),
    ("documents_and_receipts", "Photograph the best-before date on any item in your kitchen", "the best-before or use-by date on any packaged food in your kitchen, with the product name visible"),
]


def dollar_tasks() -> list[dict]:
    return [{
        "type": "do", "title": title, "location": "Remote", "effortMinutes": 1, "difficulty": "easy", "pricePerWorker": 1_000_000,
        "acceptance": "One photo taken now with the capture code in the shot and the subject readable, and what it shows typed out",
        "payload": {"category": cat, "instructions": f"Photograph {what}. One photo with your phone's camera, not a screenshot.{CODE_RULE} Then type: {WRITE[title].lower()}.", "proof": "photos", "write": WRITE[title]},
        "timeLimitSeconds": 900,
    } for cat, title, what in DOLLAR]
