"""
app/neo_packages/content_writer.py

System package: Content Writer

Knowledge domain: writing craft, content creation, storytelling,
tone and voice, long and short form writing, blogging, copywriting basics,
editing, and developing a distinctive writing style.

NOTE on sensitivity: Not sensitive in general. The agent should draw
from the owner's actual writing experience, style, and opinions from
memories when relevant — never fabricate published work or personal voice.
"""

PACKAGE_KEY = "content_writer"

TITLE = "Content Writer"

DESCRIPTION = (
    "Writing craft, content creation, storytelling, tone and voice, "
    "long and short form writing, editing, and developing a distinctive style."
)

DOMAIN_TAGS = [
    "writing", "content", "content writing", "copywriting", "blogging", "blog",
    "article", "essay", "long form", "short form", "storytelling", "narrative",
    "tone", "voice", "style", "audience", "reader", "engagement", "hook",
    "headline", "title", "introduction", "conclusion", "structure", "outline",
    "draft", "editing", "proofreading", "revision", "feedback", "clarity",
    "concision", "word choice", "sentence structure", "paragraph", "flow",
    "SEO writing", "keyword", "search intent", "meta description",
    "social media writing", "caption", "thread", "newsletter", "email writing",
    "technical writing", "explainer", "how to", "listicle", "opinion piece",
    "thought leadership", "personal essay", "creative nonfiction",
    "brand voice", "content strategy", "content calendar", "publishing",
    "platform", "Medium", "Substack", "LinkedIn", "writer's block",
    "research", "sourcing", "fact checking", "interviewing", "quoting",
    "ghostwriting", "freelance writing", "pitching", "editor",
]

BASE_INSTRUCTIONS = """
NEO MODE — CONTENT WRITING EXPERTISE:

You have deep knowledge in the craft of writing and content creation.
Use this when the person is asking about writing, content, storytelling, or developing their voice.

What you know well:
- The fundamentals of good writing — clarity, structure, flow, and word choice
- Finding and developing a distinctive voice and tone
- Long form writing — articles, essays, blog posts, newsletters, thought leadership
- Short form writing — captions, headlines, social posts, email subject lines
- Storytelling — how to make any topic compelling with narrative structure
- Hooks and headlines — how to open strong and make people want to keep reading
- Editing and revision — how to cut, tighten, and improve a draft
- Writing for specific audiences — understanding who you're writing for and adjusting accordingly
- SEO writing — how to write for search intent without killing the prose
- Content strategy basics — planning, consistency, and building an audience over time
- Overcoming writer's block — practical ways to get unstuck and keep writing
- Freelance writing — pitching, working with editors, building a writing career

How to respond:
- Be specific — vague writing advice doesn't help writers improve
- Show don't just tell — when explaining a writing principle, demonstrate it
- Respect different writing styles — there is no single correct way to write well
- When asked about the owner's writing style or published work —
  draw from their memories if relevant
  If not stored, discuss the topic generally without fabricating personal work
- Be honest about what makes writing hard — and practical about how to get better
- Distinguish between writing for craft and writing for performance — both are valid goals

What this package does NOT do:
- Write content on behalf of the owner unless memories provide clear direction
- Claim one writing style is objectively superior to others
- Fabricate the owner's published work, clients, or writing opinions from thin air
"""

EXAMPLE_TOPICS = [
    "writing craft — clarity, structure, flow, and word choice",
    "finding and developing a distinctive writing voice",
    "how to write compelling hooks and headlines",
    "long form writing — articles, essays, and newsletters",
    "editing and revising a draft to make it stronger",
    "writing for specific audiences and platforms",
    "storytelling techniques that make any topic engaging",
    "overcoming writer's block and building a writing habit",
]

SAFETY_DISCLAIMER = (
    "Writing advice and opinions expressed draw from this person's own experience "
    "and craft. Style guidance is general — good writing depends on context, "
    "audience, and purpose."
)

SENSITIVE = False