"""LLM writing layer for Today (Understand) and Regulate. Same division of
labor as llm.py's Season prompt: which dimensions are active, what
practice type was matched, and whether human/chart data disagree are all
decided in code (daily_dimensions.py / regulate.py) before any model call
-- these prompts only turn already-decided facts into plain language.
"""

from __future__ import annotations

import os

from anthropic import Anthropic

from astroengine.daily_dimensions import DAILY_DIMENSIONS
from prompts import HARD_RULES, JARGON_BAN, SYMBOLIC_FRAMING_RULE

MODEL = os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-5")

DIMENSION_KEYS = list(DAILY_DIMENSIONS.keys())

TODAY_SYSTEM_PROMPT = f"""You are writing today's plain-language snapshot for a personal \
wellness app. The reader should never need to know any astrology to understand this -- it \
should read like a perceptive friend naming what's going on, not a chart report.

You will receive today's ACTIVE dimensions (only ones with real signal -- inactive dimensions \
are not sent to you and must be left null in your output) with a tier (strong signal / notable \
/ minor undertone) and a character (expansive / contractive / mixed), grounded in real \
calculated evidence for each.

{JARGON_BAN}

{SYMBOLIC_FRAMING_RULE}

{HARD_RULES}

FORMAT: one or two plain sentences per active dimension, in the voice of direct observation \
("You're in a period that may feel more emotionally demanding than usual" / "Your energy is \
more outward and expansive right now" / "This is a quieter stretch for connection -- you don't \
need to force it"). Calibrate directness to tier exactly as in Season copy: strong signal = more \
direct, notable = softer ("there's a thread of..."), minor undertone = brief footnote.

If NO dimension is active at all, do not write any dimension text -- instead write ONE \
overall_note in the same voice, plainly saying today reads as quiet and steady, nothing pulling \
hard in any direction. Never invent activity that isn't in the data.

Write directly into the write_today tool."""

REGULATE_SYSTEM_PROMPT = f"""You are writing a short, usable wellness practice for a personal \
app, matched to a practice TYPE that has already been chosen by other logic based on the \
reader's reported mood and/or today's chart state -- you are not choosing the type, only writing \
its content.

{JARGON_BAN}

{SYMBOLIC_FRAMING_RULE}

{HARD_RULES}

You will be told whether today's chart state and the reader's reported mood point the same way \
or disagree. If they disagree, your intro must name that plainly and gently -- something like \
"Your forecast suggested a quieter stretch, but you're telling me you feel energized. Let's work \
with what you're actually experiencing" -- never tell the reader they're supposed to feel \
differently from what they reported.

FORMAT:
- intro: 1-2 sentences, warm, direct, naming what's happening and (if relevant) any mismatch.
- practice_title: a short, specific, human name for this exact practice (not just the type name).
- practice_body: the actual practice, 3-6 short steps or short paragraphs, genuinely usable right \
now (a real grounding technique, a real journaling prompt, a real breathing pattern, a real \
2-minute visualization -- concrete and specific to the matched type, not generic filler like \
"take some time for yourself").

Write directly into the write_practice tool."""


def _dimension_schema() -> dict:
    return {
        key: {"type": ["string", "null"], "description": "1-2 plain sentences, or null if this dimension wasn't active"}
        for key in DIMENSION_KEYS
    }


def generate_today_reading(natal_summary: str, active_dimensions: list[dict]) -> dict:
    """active_dimensions: [{key, label, framing, tier, character, evidence_text: [...]}].
    Returns {overall_note: str|None, dimensions: {key: str|None}}."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set -- cannot generate a reading")

    lines = ["NATAL SUMMARY (voice/color only):", natal_summary, ""]
    if not active_dimensions:
        lines.append("No dimension has real signal today -- write only overall_note.")
    else:
        for d in active_dimensions:
            lines.append(f"=== {d['label']} ({d['key']}) -- {d['framing']} ===")
            lines.append(f"  tier: {d['tier']}, character: {d['character']}")
            for e in d["evidence_text"]:
                lines.append(f"  - {e}")
    lines.append("")
    lines.append("Write today's snapshot into the write_today tool.")
    user_prompt = "\n".join(lines)

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL, max_tokens=2048, system=TODAY_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        tools=[{
            "name": "write_today",
            "description": "Submit today's plain-language snapshot.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "overall_note": {"type": ["string", "null"]},
                    "dimensions": {"type": "object", "properties": _dimension_schema(), "required": DIMENSION_KEYS},
                },
                "required": ["overall_note", "dimensions"],
            },
        }],
        tool_choice={"type": "tool", "name": "write_today"},
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == "write_today":
            return block.input
    raise RuntimeError("model did not return a write_today tool call")


PREPARE_SYSTEM_PROMPT = f"""You are writing a single short preparatory nudge for a personal \
wellness app -- one or two sentences telling the reader a meaningful, evidenced window is \
approaching soon, so they can prepare for it before it arrives. This is preparation, not \
fortune-telling: never claim a specific external event will happen.

{JARGON_BAN}

{SYMBOLIC_FRAMING_RULE}

{HARD_RULES}

FORMAT: one or two sentences, direct and useful. Name roughly how many days away it is and what \
kind of preparation might help (e.g. protecting recovery time, clearing space, or -- if the \
period reads as expansive rather than demanding -- naming that this could be a good window to \
start something). Do not use the word "forecast" more than once. Output ONLY the sentence(s), \
nothing else."""


def generate_prepare_nudge(evidence_text: str, days_away: int, character: str | None) -> str:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set -- cannot generate a reading")

    user_prompt = (
        f"Approaching window: {days_away} days away.\n"
        f"Character: {character or 'unclear'}\n"
        f"Evidence: {evidence_text}\n\n"
        "Write the nudge now."
    )
    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL, max_tokens=256, system=PREPARE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return "".join(block.text for block in response.content if block.type == "text").strip()


def generate_practice_copy(
    practice_type: str, mood: str | None, chart_state: str, human_chart_mismatch: bool, driven_by: str,
) -> dict:
    """Returns {intro, practice_title, practice_body}."""
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set -- cannot generate a reading")

    lines = [
        f"Matched practice type: {practice_type}",
        f"Reported mood today: {mood if mood else '(no check-in yet)'}",
        f"Today's chart state (internal label, do not surface): {chart_state}",
        f"Match was driven by: {driven_by}",
        f"Chart/human mismatch: {'yes -- name it gently in the intro' if human_chart_mismatch else 'no'}",
        "",
        "Write the practice into the write_practice tool.",
    ]
    user_prompt = "\n".join(lines)

    client = Anthropic(api_key=api_key)
    response = client.messages.create(
        model=MODEL, max_tokens=1536, system=REGULATE_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
        tools=[{
            "name": "write_practice",
            "description": "Submit the practice.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "intro": {"type": "string"},
                    "practice_title": {"type": "string"},
                    "practice_body": {"type": "string"},
                },
                "required": ["intro", "practice_title", "practice_body"],
            },
        }],
        tool_choice={"type": "tool", "name": "write_practice"},
    )
    for block in response.content:
        if block.type == "tool_use" and block.name == "write_practice":
            return block.input
    raise RuntimeError("model did not return a write_practice tool call")
