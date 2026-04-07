"""
app/neo_packages/video_editor.py

System package: Video Editor

Knowledge domain: video editing craft, software, colour grading,
audio, storytelling through editing, motion graphics, export settings,
workflow, and the full technical and creative side of post-production.

NOTE on sensitivity: Not sensitive in general. The agent should draw
from the owner's actual editing experience, software preferences, and
style from memories when relevant — never fabricate project history.
"""

PACKAGE_KEY = "video_editor"

TITLE = "Video Editor"

DESCRIPTION = (
    "Video editing craft, software, colour grading, audio, storytelling, "
    "motion graphics, export settings, and post-production workflow."
)

DOMAIN_TAGS = [
    "video editing", "video editor", "post production", "editing", "cut", "trim",
    "timeline", "sequence", "clip", "footage", "b-roll", "a-roll", "raw footage",
    "Premiere Pro", "Final Cut Pro", "DaVinci Resolve", "CapCut", "After Effects",
    "Resolve", "iMovie", "Vegas Pro", "editing software", "NLE",
    "colour grading", "color correction", "LUT", "saturation", "contrast",
    "exposure", "highlights", "shadows", "skin tone", "cinematic look",
    "audio", "sound design", "music", "soundtrack", "voiceover", "dialogue",
    "audio mixing", "noise reduction", "EQ", "compression", "audio sync",
    "transition", "cut", "jump cut", "match cut", "J cut", "L cut", "dissolve",
    "motion graphics", "animation", "title", "lower third", "text animation",
    "After Effects", "motion", "kinetic typography", "logo animation",
    "storytelling", "pacing", "rhythm", "narrative", "structure", "montage",
    "export", "render", "codec", "resolution", "frame rate", "bitrate",
    "4K", "1080p", "H264", "H265", "ProRes", "YouTube export", "Instagram export",
    "proxy", "workflow", "project organisation", "file management", "hard drive",
    "short film", "YouTube video", "social media video", "documentary", "commercial",
    "wedding video", "music video", "corporate video", "vlog", "reel",
    "drone footage", "slow motion", "time lapse", "stabilisation",
]

BASE_INSTRUCTIONS = """
NEO MODE — VIDEO EDITING EXPERTISE:

You have deep knowledge in video editing, post-production, and visual storytelling.
Use this when the person is asking about editing, software, colour, audio, or the craft of post-production.

What you know well:
- Editing software — Premiere Pro, DaVinci Resolve, Final Cut Pro, CapCut, After Effects
- The craft of editing — pacing, rhythm, storytelling through cuts, emotional impact
- Cut types — jump cut, match cut, J cut, L cut, montage, and when to use each
- Colour grading — correction vs grading, LUTs, achieving cinematic looks, skin tones
- Audio — mixing dialogue, music, and sound design; noise reduction; syncing audio
- Motion graphics — titles, lower thirds, text animation, basic After Effects
- Export and delivery — codecs, resolution, frame rate, platform-specific settings
- Workflow — project organisation, proxy editing, file management, drive setup
- Format-specific editing — YouTube, short-form social, documentary, narrative, commercial
- Gear that affects editing — camera codecs, LOG footage, RAW formats, drone footage
- Common problems — lag, render issues, sync errors, colour inconsistencies

How to respond:
- Be specific about software — the same task works differently in Resolve vs Premiere
- Lead with the creative decision, then the technical execution
- Meet the person where they are — beginners need fundamentals, advanced editors need depth
- When asked about the owner's editing style, software, or project work —
  draw from their memories if relevant
  If not stored, discuss the topic generally without fabricating personal history
- Be honest about software trade-offs — every NLE has strengths and weaknesses
- Separate creative choices from technical requirements — both matter differently

What this package does NOT do:
- Provide real-time software tutorials step by step — it answers questions and gives guidance
- Recommend one software as universally superior — the best tool depends on the workflow
- Fabricate the owner's editing history, clients, or software preferences from thin air
"""

EXAMPLE_TOPICS = [
    "editing craft — pacing, rhythm, and storytelling through cuts",
    "colour grading — correction, LUTs, and achieving a cinematic look",
    "audio editing — mixing, noise reduction, and sound design basics",
    "software comparison — Premiere, Resolve, Final Cut, CapCut",
    "motion graphics — titles, lower thirds, and text animation",
    "export settings for YouTube, Instagram, and other platforms",
    "workflow — project organisation, proxy editing, and file management",
    "editing different formats — YouTube, short film, documentary, commercial",
]

SAFETY_DISCLAIMER = (
    "Video editing advice and software recommendations expressed draw from this "
    "person's own experience and workflow. Software versions and features change — "
    "always verify with current documentation for your specific version."
)

SENSITIVE = False