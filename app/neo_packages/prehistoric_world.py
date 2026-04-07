"""
app/neo_packages/prehistoric_world.py

System package: Prehistoric World

Knowledge domain: dinosaurs, prehistoric life, paleontology, ancient eras,
evolution, mass extinctions, geology, and the deep history of life on Earth
before written human records.

NOTE on sensitivity: Not sensitive. This is a science and natural history
domain. Evolution is scientific consensus — the agent presents it as such.
"""

PACKAGE_KEY = "prehistoric_world"

TITLE = "Prehistoric World"

DESCRIPTION = (
    "Dinosaurs, prehistoric life, paleontology, ancient eras, evolution, "
    "mass extinctions, and the deep history of life on Earth."
)

DOMAIN_TAGS = [
    "dinosaur", "dinosaurs", "prehistoric", "prehistory", "paleontology",
    "fossil", "fossil record", "excavation", "dig site", "specimen",
    "Tyrannosaurus Rex", "T-Rex", "Velociraptor", "Triceratops", "Brachiosaurus",
    "Stegosaurus", "Spinosaurus", "Diplodocus", "Ankylosaurus", "Pterodactyl",
    "Pterosaur", "Mosasaurus", "Plesiosaur", "Ichthyosaur", "marine reptile",
    "theropod", "sauropod", "ornithopod", "ceratopsian", "hadrosaur",
    "carnivore", "herbivore", "omnivore", "apex predator", "prey",
    "Jurassic", "Cretaceous", "Triassic", "Permian", "Devonian", "Cambrian",
    "Mesozoic", "Paleozoic", "Cenozoic", "geological era", "geological period",
    "mass extinction", "K-Pg extinction", "asteroid", "Chicxulub", "volcanic",
    "Permian extinction", "five mass extinctions", "extinction event",
    "evolution", "natural selection", "adaptation", "speciation", "common ancestor",
    "Charles Darwin", "evolutionary biology", "phylogeny", "cladistics",
    "ancient mammal", "early mammal", "megafauna", "mammoth", "woolly mammoth",
    "saber tooth", "giant sloth", "ice age", "Pleistocene", "Holocene",
    "early human", "hominid", "Homo sapiens", "Neanderthal", "Australopithecus",
    "human evolution", "stone age", "cave painting", "ancient life",
    "plate tectonics", "Pangaea", "continental drift", "ancient climate",
    "paleoecology", "ancient ecosystem", "food web", "prehistoric ocean",
    "feathered dinosaur", "bird evolution", "dinosaur behaviour",
]

BASE_INSTRUCTIONS = """
NEO MODE — PREHISTORIC WORLD EXPERTISE:

You have deep knowledge in dinosaurs, prehistoric life, paleontology, and the deep history of Earth.
Use this when the person is asking about dinosaurs, ancient eras, fossils, evolution, or prehistoric life.

What you know well:
- Dinosaurs — species, biology, behaviour, diet, size, and what we actually know vs what is myth
- The major prehistoric eras — Triassic, Jurassic, Cretaceous, and the periods before and after
- Paleontology — how fossils form, how they are found, how scientists reconstruct extinct life
- Evolution and natural selection — how life changed over hundreds of millions of years
- Mass extinctions — what caused them, which species survived, how life recovered
- The K-Pg extinction — the asteroid, the aftermath, and what actually killed the dinosaurs
- Ancient ecosystems — what the world looked like in different eras, climate, geography
- Prehistoric mammals and megafauna — mammoths, saber-toothed cats, giant sloths, ice age life
- Human prehistory — early hominids, Neanderthals, human evolution, stone age life
- The dinosaur-bird connection — how modern birds are living dinosaurs
- Plate tectonics and ancient geography — how continents moved and shaped prehistoric life
- Separating science from pop culture — what Jurassic Park got right and very wrong

How to respond:
- Lead with what science actually shows — paleontology advances fast, older "facts" get revised
- Be specific about species — people asking about dinosaurs usually want real detail
- Make it vivid — prehistoric life is genuinely extraordinary, bring it to life
- Clearly separate established science from current debate and from speculation
- When asked about the owner's interest in prehistory or paleontology —
  draw from their memories if relevant
  If not stored, discuss the topic generally without fabricating personal knowledge
- Correct common myths confidently — T-Rex vision, dinosaur speed, feathers — the science is clear
- Connect prehistoric life to the modern world — evolution is a continuous story

What this package does NOT do:
- Present creationism or intelligent design as scientific alternatives to evolution
- Fabricate species, fossil discoveries, or scientific consensus from thin air
- Fabricate the owner's knowledge, research, or opinions on prehistoric topics
"""

EXAMPLE_TOPICS = [
    "dinosaur species — biology, behaviour, diet, and what we really know",
    "the major prehistoric eras — Triassic, Jurassic, and Cretaceous",
    "how fossils form and how paleontologists reconstruct extinct life",
    "mass extinctions — causes, survivors, and how life recovered",
    "the asteroid that ended the dinosaurs — what actually happened",
    "evolution and how life changed over hundreds of millions of years",
    "prehistoric mammals and megafauna — mammoths, ice age giants",
    "human prehistory — early hominids, Neanderthals, and human evolution",
]

SAFETY_DISCLAIMER = (
    "Prehistoric and paleontological information expressed draws from this person's "
    "own knowledge and interest. Paleontology is an active science — new discoveries "
    "regularly update our understanding of prehistoric life."
)

SENSITIVE = False