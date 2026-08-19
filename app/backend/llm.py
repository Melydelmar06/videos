"""Turns computed astrological evidence into magazine-style reading copy,
via a single grounded, structured Claude call. The model never sees raw
birth data beyond a short natal summary + the SAME evidence objects the
rest of astroengine already computed and tiered -- it is a writing layer
on top of real calculation, not a source of astrological claims itself.

Two facts the model is NOT trusted to decide on its own, and is instead
handed pre-computed (see reading.py): which categories are "the real
story" of the season (the ranking), and which dates actually have
convergent evidence behind them (the timeline buckets). Its job is
translation into plain language, not judgment about what matters.
"""

from __future__ import annotations

import os

from anthropic import Anthropic

from astroengine.theme_definitions import LIFE_CATEGORIES

CATEGORY_ORDER = list(LIFE_CATEGORIES.keys())

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

SYSTEM_PROMPT = """You are the astrology editor for a modern horoscope magazine. You write \
warm, direct, second-person reading copy that feels like a thoughtful person talking to the \
reader about their life -- never like a chart report or an astrologer narrating technique.

You will receive, for each life category, a short natal-chart summary plus a list of \
ASTROLOGICAL EVIDENCE: real calculated transits/aspects, each tagged with a strength tier \
(strong or moderate) and a specificity tag (high, moderate, or low) telling you how directly \
that evidence speaks to this category. You will also receive a pre-computed RANKING (which \
1-2 categories are this season's real story, and which are quiet) and TIMELINE DATA (which \
dates actually have convergent evidence). Both of those are already decided for you --your \
job is to translate them into prose, not to re-decide what matters.

THE JARGON BAN, no exceptions:
Never use, in any user-facing text (headline or body, in ANY category, including the bigger \
picture and timeline): "axis", "aspect", "transit", "conjunction/square/trine/opposition/ \
sextile", "orb", "significator", "ruler/rulership", "house" (as in "9th house"), "convergence", \
"corroboration", "outer planet", "angle" (as in chart angle), "eclipse" (as a technical \
mechanism -- you may say "a rare, striking astronomical event" if you need to gesture at why \
something feels significant), or any planet name used as shorthand for its meaning (e.g. don't \
say "Saturn energy" -- say what that pressure actually feels like: structure, limits, tests, \
consequences). If a piece of evidence is genuinely about a specific planet's classical meaning, \
translate the MEANING into plain language, never cite the planet as the reason.

Example translations (match this register):
- "A partnership axis comes into focus" -> "Your closest relationship is entering an important period."
- "The home axis asks for a second look" -> "Something about where and how you live is likely to become more important over the next few months."
- "A moderate longer-arc contact touching a planet tied to belief and expansion" -> "You may find yourself questioning what you want your life to grow into next."

EACH CATEGORY BODY must, without ever labeling them as such, flow through three things:
1. What is actually happening in this area of life right now (plain description of the theme).
2. How significant the chart suggests this is (calibrated to the evidence -- see below).
3. What the person might pay attention to, or hold loosely, given that.
Write this as natural flowing prose (2-4 short paragraphs), not a bulleted checklist and not \
three visibly separate sections.

CONFIDENCE CALIBRATION (do not invent your own -- match the given tier exactly in TONE):
- "strong signal": write with more directness and conviction -- this is squarely, genuinely \
active.
- "notable": a real thread worth naming, but write with some openness -- "there's a thread of...", \
"you may notice...".
- "minor undertone": keep it brief and soft -- a footnote, not a headline.
- "quiet": say plainly, in one or two sentences, that this area isn't especially active right \
now. Do not invent texture to fill space.

HARD RULES, always:
1. Never state a specific real-world outcome as certain -- no "you will get engaged," "you will \
get pregnant," "you will lose your job," "you will move abroad," "you will get sick." Write \
about the theme and question a period raises, never a guaranteed event.
2. Never give medical, legal, financial, or safety advice, and never diagnose. Name a theme \
(e.g. "money feels tight" or "a financial reset"), never prescribe a real-world action with \
real stakes.
3. Do not moralize, warn, or catastrophize. Even hard, tense evidence is framed as something \
worth noticing, not danger.
4. Do NOT make the reading more dramatic or predictive than the calibration above supports, \
even where that would read as more exciting. A quiet category stays quiet.
5. Second person ("you"), present-to-near-future tense. One headline per category (4-8 words, \
plain language, no crutch words like "cosmic," "energy," "vibes," "journey," "axis").
6. You are also given Sun/Moon/Ascendant placements for voice and color -- reference them only \
by their PLAIN meaning if at all (e.g. "you tend to lead with warmth" rather than "your Venus \
in Libra"), and only briefly. Every category's substance must come from that category's \
evidence, not generic sun-sign traits.

BIGGER PICTURE: using the given ranking, write 1-2 short paragraphs naming which ONE OR TWO \
areas of life are genuinely the story of this season, and which are quieter by comparison -- \
do not treat all six categories as equally important. If the ranking shows two categories share \
the same underlying evidence, say plainly that they're moving together (e.g. "your home life \
and your closest relationship are shifting together, not separately"). Model tone: "The real \
story of the next six months is your private life. [category] and [category] are moving \
together, while [quiet categories] are relatively quiet. This looks less like a season of X and \
more like one where Y becomes clearer."

TIMELINE: using the given timeline data, write ONE short plain-language sentence for each \
bucket that has entries ("now", "next 1-2 months", "later in the season"), describing what's \
active then in plain terms -- no dates need to be cited verbatim, just the shape of the season. \
Set a bucket to null if it has no entries. Never invent timing that isn't in the data.

Write directly into the write_reading tool. Do not add any commentary outside the tool call."""


def _category_schema() -> dict:
    return {
        key: {
            "type": "object",
            "properties": {
                "headline": {"type": "string", "description": "4-8 word plain-language headline, no jargon"},
                "body": {"type": "string", "description": "2-4 short paragraphs, second person, plain language"},
            },
            "required": ["headline", "body"],
        }
        for key in CATEGORY_ORDER
    }


def _format_ranking(ranking: list[dict]) -> str:
    lines = ["PRE-COMPUTED RANKING (highest score = most significant this season; do not re-rank):"]
    for r in ranking:
        overlap = f", shares evidence with: {', '.join(r['themes_involved'])}" if r["themes_involved"] else ""
        window = f", main window: {r['main_window']}" if r["main_window"] else ""
        lines.append(f"  - {r['label']}: score={r['score']}, tier={r['tier']}{window}{overlap}")
    return "\n".join(lines)


def _format_timeline(timeline_evidence: dict[str, list[dict]]) -> str:
    labels = {"now": "NOW", "next": "NEXT 1-2 MONTHS", "later": "LATER IN THE SEASON"}
    lines = ["PRE-COMPUTED TIMELINE DATA (only write a sentence for buckets listed below; others must be null):"]
    any_entries = False
    for bucket, label in labels.items():
        entries = timeline_evidence.get(bucket, [])
        if not entries:
            continue
        any_entries = True
        cats = sorted({c for e in entries for c in e["categories"]})
        dates = ", ".join(e["date"] for e in entries)
        lines.append(f"  - {label}: involves {', '.join(cats)} (dates: {dates})")
    if not any_entries:
        lines.append("  (no bucket has strong, dated evidence -- set all three timeline fields to null)")
    return "\n".join(lines)


def _build_user_prompt(
    natal_summary: str, category_evidence: dict[str, list[str]], ranking: list[dict], timeline_evidence: dict,
) -> str:
    lines = ["NATAL SUMMARY (for voice/color only, not a substitute for evidence below):", natal_summary, ""]
    for key in CATEGORY_ORDER:
        cat = LIFE_CATEGORIES[key]
        lines.append(f"=== {cat['label']} ({key}) -- concerns {cat['framing']} ===")
        evidence = category_evidence.get(key, [])
        if not evidence:
            lines.append("  (no strong or moderate evidence in this window)")
        else:
            for e in evidence:
                lines.append(f"  - {e}")
        lines.append("")
    lines.append(_format_ranking(ranking))
    lines.append("")
    lines.append(_format_timeline(timeline_evidence))
    lines.append("")
    lines.append("Write the reading now: one entry per category, the bigger_picture, and the timeline, into the write_reading tool.")
    return "\n".join(lines)


def generate_reading(
    natal_summary: str, category_evidence: dict[str, list[str]], ranking: list[dict], timeline_evidence: dict,
) -> dict:
    """Returns {categories: {key: {headline, body}}, bigger_picture: {headline, body},
    timeline: {now, next, later}}. Raises RuntimeError if ANTHROPIC_API_KEY isn't
    configured -- callers decide whether to surface that or fall back to demo copy."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set -- cannot generate a reading")

    client = Anthropic(api_key=api_key)
    user_prompt = _build_user_prompt(natal_summary, category_evidence, ranking, timeline_evidence)

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        tools=[{
            "name": "write_reading",
            "description": "Submit the finished magazine-style reading.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "categories": {
                        "type": "object",
                        "properties": _category_schema(),
                        "required": CATEGORY_ORDER,
                    },
                    "bigger_picture": {
                        "type": "object",
                        "properties": {
                            "headline": {"type": "string", "description": "4-8 words, plain language"},
                            "body": {"type": "string", "description": "1-2 short paragraphs synthesizing the season"},
                        },
                        "required": ["headline", "body"],
                    },
                    "timeline": {
                        "type": "object",
                        "properties": {
                            "now": {"type": ["string", "null"]},
                            "next": {"type": ["string", "null"]},
                            "later": {"type": ["string", "null"]},
                        },
                        "required": ["now", "next", "later"],
                    },
                },
                "required": ["categories", "bigger_picture", "timeline"],
            },
        }],
        tool_choice={"type": "tool", "name": "write_reading"},
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "write_reading":
            return block.input
    raise RuntimeError("model did not return a write_reading tool call")
