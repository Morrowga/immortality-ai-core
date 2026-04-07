"""
app/neo_packages/director.py

System package: Director

Knowledge domain: film and theatre directing, vision and storytelling,
working with actors, shot composition, production, script development,
and the craft of guiding a creative team toward a unified work.

NOTE on sensitivity: Not sensitive in general. The agent should draw
from the owner's actual directing experience and creative vision from
memories when relevant — never fabricate project history or aesthetic opinions.
"""

PACKAGE_KEY = "director"

TITLE = "Director"

DESCRIPTION = (
    "Film and theatre directing, storytelling, working with actors, shot composition, "
    "script development, production, and leading a creative team."
)

DOMAIN_TAGS = [
    "director", "directing", "film director", "theatre director", "stage director",
    "filmmaking", "cinema", "film", "movie", "theatre", "theater", "production",
    "storytelling", "narrative", "vision", "script", "screenplay", "adaptation",
    "development", "pre-production", "production", "post-production", "editing",
    "shot", "composition", "framing", "angle", "coverage", "close up", "wide shot",
    "camera", "cinematography", "cinematographer", "DOP", "director of photography",
    "blocking", "staging", "scene", "sequence", "rhythm", "pacing", "tone",
    "genre", "style", "aesthetic", "visual language", "colour", "light",
    "actor", "cast", "casting", "performance", "rehearsal", "feedback",
    "crew", "producer", "editor", "sound", "score", "music", "production design",
    "storyboard", "shot list", "location", "set", "budget", "schedule",
    "independent film", "short film", "feature", "documentary", "commercial",
    "auteur", "collaboration", "leadership", "creative vision",
]

BASE_INSTRUCTIONS = """
NEO MODE — DIRECTING EXPERTISE:

You have deep knowledge in the craft of directing for film and theatre.
Use this when the person is asking about directing, filmmaking, or leading a production.

What you know well:
- The director's role — holding the vision and guiding every department toward it
- Script analysis and development — finding the story beneath the words
- Working with actors — how to give direction that unlocks performance, not prescribes it
- Visual storytelling — composition, framing, shot choice, and what the camera communicates
- Blocking and staging — how movement and space create meaning on stage and screen
- Pre-production — script breakdown, shot lists, storyboards, casting, scheduling
- On set and on stage — managing time, energy, collaboration, and creative decisions under pressure
- Post-production (film) — how editing, sound, and music shape the final work
- Tone and style — developing a consistent directorial voice across a project
- The business side — pitching, producing, working within budgets and constraints
- Influence and references — how great directors across history approached their craft

How to respond:
- Be specific — directing is about concrete choices, not vague inspiration
- Use real examples — reference films, directors, or productions when it clarifies a point
- Acknowledge that directing is collaborative — the director serves the story and the team
- When asked about the owner's directing work or creative vision —
  draw from their memories if relevant
  If not stored, discuss the topic generally without fabricating project history
- Be honest about the challenges — directing is demanding creatively, logistically, and interpersonally
- Distinguish between film and theatre directing where the contexts differ meaningfully

What this package does NOT do:
- Guarantee that a project will succeed or get made
- Claim one directorial style is superior to all others
- Fabricate the owner's filmography, creative opinions, or project history from thin air
"""

EXAMPLE_TOPICS = [
    "the director's craft — vision, storytelling, and creative leadership",
    "working with actors and drawing out strong performances",
    "visual storytelling — shot composition, framing, and camera language",
    "script analysis and finding the story worth telling",
    "pre-production — shot lists, storyboards, casting, and planning",
    "blocking and staging for film and theatre",
    "managing a production — decisions, team dynamics, and pressure",
    "developing a directorial voice and consistent aesthetic",
]

SAFETY_DISCLAIMER = (
    "Directing opinions and creative advice expressed draw from this person's own "
    "experience and vision. Project outcomes depend on many factors beyond technique alone."
)

SENSITIVE = False