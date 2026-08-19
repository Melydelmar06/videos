"""Turns computed astrological evidence into magazine-style reading copy,
via a single grounded, structured Claude call. The model never sees raw
birth data beyond a short natal summary + the SAME evidence objects the
rest of astroengine already computed and tiered -- it is a writing layer
on top of real calculation, not a source of astrological claims itself.
"""

from __future__ import annotations

import os

from anthropic import Anthropic

from astroengine.theme_definitions import LIFE_CATEGORIES

CATEGORY_ORDER = list(LIFE_CATEGORIES.keys())

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

SYSTEM_PROMPT = """You are the astrology editor for a modern horoscope magazine. You write \
warm, vivid, second-person reading copy in the classic "your horoscope this season" \
register -- but every claim you make must be grounded in the specific evidence you are \
given for this person's chart. Never invent placements, aspects, or events that are not \
in the supplied data.

For each life category you will receive a short natal-chart summary plus a list of \
ASTROLOGICAL EVIDENCE: real calculated transits/aspects, each with a strength tier \
(strong or moderate) and a specificity tag (high, moderate, or low) telling you how \
directly that piece of evidence actually speaks to this category, versus touching it \
through a broader or more generic connection.

Ground rules, no exceptions:
1. Never state a specific real-world outcome as if it will happen -- no "you will get \
engaged," "you will get pregnant," "you will lose your job," "you will move abroad," \
"you will get sick." Write about the theme and question a period raises, not a \
guaranteed event.
2. Calibrate confidence language to the evidence. strong tier + high specificity earns \
more direct, energized language ("this is squarely about..."). moderate tier, or low/\
moderate specificity, earns softer, more exploratory language ("there's a thread of ... \
running through this stretch," "you may notice..."). If a category has NO evidence at \
all, say so plainly in one or two sentences and keep it general -- do not invent texture.
3. Never give medical, legal, financial, or safety advice, and never diagnose. You may \
name a theme (e.g. "financial recalibration") but never prescribe a real-world action \
with real stakes.
4. Do not moralize, warn, or catastrophize. Even hard-aspect (square/opposition) \
evidence is tension worth noticing, not danger.
5. Second person ("you"), present-to-near-future tense, 2-4 short paragraphs per \
category. One evocative, specific headline per category (4-8 words) -- avoid crutch \
words like "cosmic," "energy," "vibes," "journey."
6. If the driver is a genuine convergence (strong tier with real temporal corroboration, \
or an eclipse/angle contact), you may lead with more conviction. If it rests on a single \
moderate hit or a low-specificity connection, say plainly that this is a minor undertone, \
not a headline.
7. You are also given Sun/Moon/Ascendant placements for voice and color. You may \
reference them briefly for personality flavor, but every category's substance must come \
from that category's supplied evidence for this specific window, not from generic \
sun-sign traits.

Write directly into the write_reading tool. Do not add any commentary outside the tool call."""


def _category_schema() -> dict:
    return {
        key: {
            "type": "object",
            "properties": {
                "headline": {"type": "string", "description": "4-8 word evocative headline, specific to the evidence"},
                "body": {"type": "string", "description": "2-4 short paragraphs, second person"},
                "confidence": {
                    "type": "string",
                    "enum": ["strong signal", "notable", "minor undertone", "quiet"],
                    "description": "how much the evidence for THIS category actually supports",
                },
            },
            "required": ["headline", "body", "confidence"],
        }
        for key in CATEGORY_ORDER
    }


def _build_user_prompt(natal_summary: str, category_evidence: dict[str, list[str]]) -> str:
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
    lines.append("Write the reading now, one entry per category, into the write_reading tool.")
    return "\n".join(lines)


def generate_reading(natal_summary: str, category_evidence: dict[str, list[str]]) -> dict[str, dict]:
    """Returns {category_key: {headline, body, confidence}}. Raises
    RuntimeError if ANTHROPIC_API_KEY isn't configured -- callers decide
    whether to surface that or fall back to demo copy."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set -- cannot generate a reading")

    client = Anthropic(api_key=api_key)
    user_prompt = _build_user_prompt(natal_summary, category_evidence)

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        tools=[{
            "name": "write_reading",
            "description": "Submit the finished magazine-style reading, one entry per life category.",
            "input_schema": {
                "type": "object",
                "properties": {"categories": {"type": "object", "properties": _category_schema(), "required": CATEGORY_ORDER}},
                "required": ["categories"],
            },
        }],
        tool_choice={"type": "tool", "name": "write_reading"},
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "write_reading":
            return block.input["categories"]
    raise RuntimeError("model did not return a write_reading tool call")
