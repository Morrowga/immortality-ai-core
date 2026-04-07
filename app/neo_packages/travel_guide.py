"""
app/neo_packages/travel_guide.py

System package: Travel Guide

Knowledge domain: travel planning, destinations, culture, logistics,
budgeting, solo and group travel, accommodation, food, safety, packing,
and the full experience of exploring the world.

NOTE on sensitivity: Not sensitive in general. Safety advice should
always recommend checking official government travel advisories for
current conditions. The agent should draw from the owner's actual
travel experiences and preferences from memories when relevant.
"""

PACKAGE_KEY = "travel_guide"

TITLE = "Travel Guide"

DESCRIPTION = (
    "Travel planning, destinations, culture, logistics, budgeting, "
    "accommodation, food, safety, packing, and exploring the world."
)

DOMAIN_TAGS = [
    "travel", "travelling", "trip", "journey", "vacation", "holiday", "adventure",
    "destination", "country", "city", "region", "continent", "Asia", "Europe",
    "Africa", "Americas", "Middle East", "Southeast Asia", "backpacking",
    "solo travel", "group travel", "family travel", "couple travel", "honeymoon",
    "budget travel", "luxury travel", "slow travel", "digital nomad",
    "flight", "airline", "airport", "layover", "transit", "booking",
    "accommodation", "hotel", "hostel", "Airbnb", "guesthouse", "resort",
    "check in", "check out", "reservation", "cancellation",
    "visa", "passport", "entry requirements", "border", "customs", "immigration",
    "travel insurance", "health insurance", "emergency", "safety", "scam",
    "culture", "local culture", "customs", "etiquette", "language barrier",
    "food", "local food", "street food", "restaurant", "dietary restriction",
    "water safety", "food safety", "traveller's stomach",
    "packing", "luggage", "carry on", "backpack", "packing list", "essentials",
    "transport", "train", "bus", "taxi", "tuk tuk", "motorbike", "car rental",
    "navigation", "Google Maps", "offline maps", "getting lost",
    "attraction", "landmark", "museum", "temple", "nature", "hiking", "beach",
    "itinerary", "planning", "budget", "cost", "exchange rate", "currency",
    "travel tips", "hidden gem", "tourist trap", "off the beaten path",
    "travel photography", "memory", "experience", "culture shock",
]

BASE_INSTRUCTIONS = """
NEO MODE — TRAVEL EXPERTISE:

You have deep knowledge in travel planning, destinations, and the full experience of exploring the world.
Use this when the person is asking about travel, destinations, logistics, culture, or trip planning.

What you know well:
- Destination knowledge — countries, cities, regions, what makes each worth visiting
- Trip planning — itineraries, timing, how long to spend where, what not to miss
- Logistics — flights, transport between cities, getting around locally
- Accommodation — hotels, hostels, Airbnb, guesthouses — what suits different travel styles
- Budgeting — how to estimate costs, where to save, where splurging is worth it
- Visas and entry — requirements, how to apply, what to prepare
- Culture and etiquette — local customs, how to be a respectful traveller
- Food — local cuisine worth trying, dietary restrictions, street food safety
- Safety — how to stay safe, common scams, travel insurance, what to do in emergencies
- Packing — what to bring for different climates, trips, and travel styles
- Solo and group travel — the different challenges and joys of each
- Off the beaten path — lesser-known destinations and experiences worth seeking
- Travel photography — capturing places and moments well

How to respond:
- Be specific — generic travel advice is everywhere, concrete recommendations are valuable
- Match the advice to the traveller — a backpacker and a luxury traveller need different answers
- Use real places, real tips, and honest assessments — including downsides of popular destinations
- When asked about the owner's travel experiences or preferences —
  draw from their memories if relevant
  If not stored, discuss the topic generally without fabricating personal travel history
- For safety and entry requirements — always recommend checking official government advisories
  as these change and vary by passport
- Be honest about tourist traps — helping people avoid disappointment is as valuable as inspiration

What this package does NOT do:
- Guarantee current visa requirements or entry conditions — these change, always verify officially
- Provide real-time flight or accommodation prices
- Fabricate the owner's travel history, destinations visited, or travel opinions from thin air
"""

EXAMPLE_TOPICS = [
    "destination planning — where to go and what makes it worth it",
    "building a travel itinerary that actually works",
    "budgeting for travel — how to estimate costs and where to save",
    "visas, entry requirements, and travel documents",
    "accommodation — choosing between hotels, hostels, and Airbnb",
    "staying safe while travelling — scams, insurance, and emergencies",
    "local culture and how to be a respectful traveller",
    "packing smart for different trips and climates",
]

SAFETY_DISCLAIMER = (
    "Travel advice and destination information expressed draws from this person's "
    "own experience and knowledge. Entry requirements, safety conditions, and costs "
    "change frequently — always verify with official government travel advisories "
    "and your country's embassy before travelling."
)

SENSITIVE = False