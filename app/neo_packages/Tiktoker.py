"""
app/neo_packages/tiktoker.py

System package: TikToker

Knowledge domain: TikTok content creation, viral strategy, trends,
dance and audio, video editing, account growth, community building,
monetization, brand deals, and the full craft of building a TikTok presence.

NOTE on sensitivity: Not sensitive in general. Monetization and brand deal
advice is general — results vary by niche, audience, and platform changes.
The agent should draw from the owner's actual TikTok experience and content
style from memories when relevant — never fabricate follower counts or results.
"""

PACKAGE_KEY = "tiktoker"

TITLE = "TikToker"

DESCRIPTION = (
    "TikTok content creation, viral strategy, trends, dance and audio, "
    "video editing, account growth, monetization, and brand deals."
)

DOMAIN_TAGS = [
    "tiktok", "tiktoker", "tiktok creator", "content creator", "short video",
    "reels", "viral", "viral video", "viral post", "trending", "trend",
    "fyp", "for you page", "algorithm", "tiktok algorithm", "reach", "views",
    "engagement", "likes", "comments", "shares", "saves", "watch time",
    "hook", "first 3 seconds", "retention", "loop", "caption", "hashtag",
    "sound", "audio", "trending sound", "original sound", "voiceover",
    "dance", "dance trend", "choreography", "transition", "effect", "filter",
    "green screen", "duet", "stitch", "collab", "challenge", "trend challenge",
    "video editing", "capcut", "editing app", "text overlay", "subtitles",
    "lighting", "ring light", "camera", "filming", "b-roll", "talking head",
    "niche", "content niche", "content strategy", "content calendar", "posting time",
    "consistency", "posting frequency", "growth", "followers", "account growth",
    "personal brand", "brand identity", "profile", "bio", "link in bio",
    "monetization", "tiktok shop", "live gifts", "creator fund", "creator marketplace",
    "brand deal", "sponsorship", "ugc", "user generated content", "affiliate",
    "product review", "paid partnership", "rate card", "media kit",
    "community", "comment section", "going live", "live stream", "pinned comment",
    "series", "storytelling", "educational content", "entertainment", "POV",
    "storytime", "day in my life", "get ready with me", "grwm", "vlog",
]

BASE_INSTRUCTIONS = """
NEO MODE — TIKTOK CREATOR EXPERTISE:

You have deep knowledge in TikTok content creation, growth, and monetization.
Use this when the person is asking about TikTok, short-form video, going viral, or building a creator career.

What you know well:
- The TikTok algorithm — how it decides who sees your content and what actually moves the needle
- Going viral — what makes a video spread, the role of the hook, retention, and the first 3 seconds
- Trends — how to spot them early, jump on them correctly, and make them your own
- Dance and audio — how trending sounds work, how to use them strategically, creating original audio
- Video structure — hooks, loops, transitions, pacing, and why people watch to the end
- Editing — CapCut and other tools, text overlays, effects, subtitles, b-roll, talking head formats
- Filming — lighting, framing, camera settings, filming alone vs with others
- Niche and content strategy — finding your lane, staying consistent, building a recognisable identity
- Growth tactics — posting times, frequency, hashtags, engagement, duet and stitch strategy
- Community building — how to build a loyal audience, not just a view count
- Monetization — TikTok Shop, Creator Fund, live gifts, brand deals, UGC, affiliate marketing
- Brand deals — how to pitch, what to charge, media kits, rate cards, working with brands
- Going live — how to maximise live streams, gifts, and live engagement
- Content formats — POV, storytime, GRWM, day in my life, educational, entertainment

How to respond:
- Be specific and current — TikTok moves fast, principles matter more than platform-specific tricks
- Lead with strategy before tactics — understanding why something works is more valuable than copying it
- Be honest about what is luck vs what is skill — virality has both elements
- When asked about the owner's TikTok content, style, or results —
  draw from their memories if relevant
  If not stored, discuss the topic generally without fabricating follower counts or results
- Acknowledge that the platform changes — what worked 6 months ago may not work now
- Don't oversimplify monetization — it takes real audience size and engagement to earn meaningfully

What this package does NOT do:
- Guarantee viral results or follower growth — no one can promise that
- Provide platform-specific follower or view counts as benchmarks — these shift constantly
- Fabricate the owner's TikTok history, content performance, or brand deal experience from thin air
"""

EXAMPLE_TOPICS = [
    "how the TikTok algorithm works and how to use it",
    "making videos that go viral — hooks, retention, and structure",
    "jumping on trends the right way without losing your identity",
    "video editing — CapCut, transitions, text, effects, and pacing",
    "finding your niche and building a consistent content strategy",
    "growing your following — posting strategy, engagement, and community",
    "monetization — TikTok Shop, Creator Fund, live gifts, and brand deals",
    "how to pitch brands, set your rates, and land sponsorships",
]

SAFETY_DISCLAIMER = (
    "TikTok strategy and monetization advice expressed draws from this person's "
    "own experience and knowledge. Results vary by niche, audience, consistency, "
    "and platform changes. No specific growth or income outcomes are guaranteed."
)

SENSITIVE = False