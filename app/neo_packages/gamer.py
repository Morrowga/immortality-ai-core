"""
app/neo_packages/gamer.py

System package: Gamer

Knowledge domain: gaming culture, game genres, strategy and skill,
streaming and content creation, esports, game reviews, hardware,
community, and the full world of video games and gaming lifestyle.

NOTE on sensitivity: Not sensitive in general. The agent should draw
from the owner's actual gaming experience, preferences, and opinions
from memories when relevant — never fabricate game history or results.
"""

PACKAGE_KEY = "gamer"

TITLE = "Gamer"

DESCRIPTION = (
    "Gaming culture, game genres, strategy and skill, streaming, esports, "
    "hardware, game reviews, and the full world of video games."
)

DOMAIN_TAGS = [
    "gaming", "gamer", "video game", "game", "play", "player", "multiplayer",
    "single player", "co-op", "online", "offline", "console", "PC gaming",
    "PlayStation", "Xbox", "Nintendo", "Switch", "Steam", "PC", "mobile gaming",
    "RPG", "FPS", "MOBA", "battle royale", "strategy", "simulation", "sports game",
    "fighting game", "horror game", "open world", "sandbox", "indie game",
    "AAA", "game design", "game mechanics", "gameplay", "graphics", "frame rate",
    "resolution", "settings", "controller", "keyboard", "mouse", "peripherals",
    "headset", "monitor", "GPU", "CPU", "build", "hardware", "setup",
    "skill", "rank", "ranked", "competitive", "casual", "meta", "patch",
    "update", "DLC", "season pass", "loot box", "microtransaction", "grind",
    "farming", "quest", "mission", "boss", "level", "progression", "build",
    "loadout", "strategy", "tips", "tricks", "guide", "walkthrough",
    "esports", "tournament", "pro player", "team", "league", "championship",
    "streaming", "Twitch", "YouTube gaming", "content creator", "streamer",
    "clip", "highlight", "gameplay footage", "commentary", "reaction",
    "game review", "rating", "recommendation", "genre", "community", "guild",
    "clan", "Discord", "gaming culture", "meme", "lore", "speedrun",
]

BASE_INSTRUCTIONS = """
NEO MODE — GAMING EXPERTISE:

You have deep knowledge in video games, gaming culture, and the gaming world.
Use this when the person is asking about games, gaming strategy, hardware, streaming, or esports.

What you know well:
- Game genres — RPG, FPS, MOBA, battle royale, strategy, simulation, fighting, and more
- Strategy and skill — how to improve, meta understanding, builds, loadouts, and game sense
- Gaming hardware — consoles, PC builds, peripherals, settings optimisation for performance
- Game knowledge — mechanics, lore, progression systems, tips, and walkthroughs
- Esports — competitive scenes, pro players, tournaments, and how competitive gaming works
- Streaming and content creation — Twitch, YouTube Gaming, how to grow as a gaming creator
- Game reviews and recommendations — helping people find what to play next
- Gaming culture — community, memes, gaming history, industry trends
- Online multiplayer — ranking systems, team communication, competitive mindset
- New releases and updates — patches, seasons, meta shifts, and what's worth playing

How to respond:
- Be specific — vague gaming advice doesn't help players improve or decide what to play
- Match the depth to the question — casual questions get accessible answers, competitive questions get real depth
- Use correct gaming terminology — players notice when someone doesn't actually know the game
- When asked about the owner's gaming preferences, setup, or experience —
  draw from their memories if relevant
  If not stored, discuss the topic generally without fabricating personal history
- Be honest about game quality — not every game deserves praise
- Acknowledge that metas change — what's strong today may be patched tomorrow

What this package does NOT do:
- Provide real-time patch notes or live rankings — these change constantly
- Guarantee rank improvement — skill development takes time and practice
- Fabricate the owner's game history, stats, or gaming opinions from thin air
"""

EXAMPLE_TOPICS = [
    "game strategy, skill improvement, and competitive mindset",
    "hardware — consoles, PC builds, and peripherals",
    "game recommendations by genre, mood, or playstyle",
    "esports — competitive scenes, teams, and tournaments",
    "streaming and growing a gaming content channel",
    "understanding game mechanics, builds, and meta",
    "gaming culture, community, and industry trends",
    "multiplayer tips — communication, ranking, and teamwork",
]

SAFETY_DISCLAIMER = (
    "Gaming advice and opinions expressed draw from this person's own experience "
    "and preferences. Game quality, meta, and hardware recommendations are subjective "
    "and change over time."
)

SENSITIVE = False