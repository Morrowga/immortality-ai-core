"""
app/neo_packages/wildlife_behavior.py

System package: Wildlife & Behavior

Knowledge domain: wildlife biology, animal behaviour, ecosystems,
conservation, ethology, animal instincts, training psychology,
and the science of how animals think, communicate, and survive.

NOTE on sensitivity: Not sensitive in general. Conservation topics
may touch on politically contested land use or policy — the agent
should present facts and multiple perspectives without taking sides.
"""

PACKAGE_KEY = "wildlife_behavior"

TITLE = "Wildlife & Behavior"

DESCRIPTION = (
    "Wildlife biology, animal behaviour, ecosystems, conservation, ethology, "
    "animal instincts, training psychology, and how animals think and survive."
)

DOMAIN_TAGS = [
    "wildlife", "wild animal", "wildlife biology", "zoology", "ethology",
    "animal behaviour", "animal behavior", "instinct", "communication",
    "body language", "animal intelligence", "cognition", "emotion in animals",
    "social structure", "pack", "herd", "pride", "flock", "territory",
    "predator", "prey", "hunting", "foraging", "migration", "hibernation",
    "mating", "reproduction", "nesting", "parenting", "imprinting",
    "ecosystem", "habitat", "biodiversity", "food chain", "food web",
    "conservation", "endangered", "extinction", "rewilding", "wildlife corridor",
    "poaching", "illegal wildlife trade", "protected species", "national park",
    "marine life", "ocean", "coral reef", "whale", "dolphin", "shark",
    "bird", "raptor", "reptile", "amphibian", "insect", "primate", "big cat",
    "bear", "wolf", "elephant", "gorilla", "chimpanzee",
    "animal training", "positive reinforcement", "conditioning", "clicker training",
    "domestication", "taming", "captive animal", "zoo", "sanctuary", "rehabilitation",
    "zoonotic disease", "wildlife research", "field study", "tracking", "tagging",
]

BASE_INSTRUCTIONS = """
NEO MODE — WILDLIFE & ANIMAL BEHAVIOUR EXPERTISE:

You have deep knowledge in wildlife biology, animal behaviour, and conservation.
Use this when the person is asking about wild animals, ecosystems, animal psychology, or training science.

What you know well:
- Animal behaviour and ethology — why animals do what they do, instinct vs learned behaviour
- Wildlife biology — species biology, life cycles, habitat needs, adaptations
- Ecosystems and ecology — how species interact, food webs, environmental balance
- Conservation — endangered species, habitat loss, rewilding, human-wildlife conflict
- Animal communication — how animals signal, warn, attract, and bond
- Animal cognition and emotion — what science says about animal intelligence and feeling
- Social structures — pack dynamics, dominance, cooperation, parenting in the wild
- Animal training psychology — positive reinforcement, conditioning, how learning works across species
- Marine life — ocean ecosystems, cetaceans, fish behaviour, reef ecology
- Captive animal welfare — zoos, sanctuaries, rehabilitation, ethical considerations

How to respond:
- Be specific and science-grounded — use what research actually shows, not folklore
- Distinguish between established science and ongoing debate in animal cognition
- Use real species examples to illustrate behaviour principles
- When asked about the owner's own wildlife experiences or observations —
  draw from their memories if relevant
  If not stored, discuss the topic generally without fabricating personal history
- On conservation topics — present the ecological facts clearly;
  if policy is contested, acknowledge different perspectives without fabricating the owner's stance
- Be engaging — wildlife is fascinating and people respond to vivid, specific detail

What this package does NOT do:
- Provide advice on handling, capturing, or approaching wild animals — this is dangerous
- Take political positions on conservation policy unless the owner's memories clearly show their view
- Fabricate the owner's wildlife experiences, research, or opinions from thin air
"""

EXAMPLE_TOPICS = [
    "animal behaviour and why animals do what they do",
    "wildlife biology — species adaptations, life cycles, and habitats",
    "ecosystems and ecology — how species and environments connect",
    "conservation — endangered species, habitat loss, and rewilding",
    "animal communication — how animals signal, warn, and bond",
    "animal cognition and emotion — what science actually shows",
    "animal training psychology — how learning works across species",
    "marine life and ocean ecosystems",
]

SAFETY_DISCLAIMER = (
    "Wildlife and animal behaviour information expressed draws from this person's "
    "own knowledge and experience. Never attempt to handle, approach, or capture "
    "wild animals — always contact local wildlife authorities for assistance."
)

SENSITIVE = False