# Aphelion — Product Architecture (V1.5 proposal)

Companion to `ARCHITECTURE.md` (the calculation/evidence engine, unchanged)
and `app/` (the V1 reading product, built and shipped). This document
covers the product layer being proposed on top of both: what Aphelion
becomes, why, and specifically what V1.5 builds versus what waits.

**Nothing in this document is implemented yet.** It's a proposal for
review. `ARCHITECTURE.md` and the existing engine (`astroengine/`) are not
touched by this change — everything here is a new layer built *on* them.

---

## 1. What Aphelion is becoming

V1 was a reading product: birth data in, a six-month horoscope-style
reading out. That reading (the "Season" experience — Bigger Picture,
category cards, timeline, "why am I seeing this") is good, tested work
and stays exactly as it is. But it was the whole product. It isn't
anymore.

**Aphelion is becoming a personal operating system for navigating your
inner life** — astrology and numerology are one input into that system,
not the product itself. The other input, equally important, is the
person's own reported experience. The system's job is to hold both,
never pretend one is the other, and get better at relating them over
time.

The core loop:

```
UNDERSTAND → REGULATE → PREPARE → REFLECT → LEARN
```

- **Understand** — what's happening with me right now, in plain language.
- **Regulate** — what's useful to do about it today, matched to actual state.
- **Prepare** — what's coming, and how to get ready before it arrives.
- **Reflect** — a lightweight daily record of what's actually true for the person.
- **Learn** — over time, does the symbolic model actually track this person's life, or not.

Explicitly *not* the product: a horoscope feed, a zodiac content app, an
astrology social network, a prediction machine, or a generic meditation
app. The astrology stays real (same evidence-strength discipline as
today), it just stops being the star of the show.

---

## 2. The foundational split: CHART data vs. HUMAN data

This is the single most important architectural decision in this
document, and everything else follows from it.

**CHART** — fully derived from birth data through `astroengine`.
Deterministic, recomputable, never influenced by anything the user
reports. Carries the exact same evidence-strength discipline the engine
already has: Strong/Moderate/Weak, background vs. temporal corroboration,
theme specificity. Nothing new is invented here — this document proposes
a new *reading* of that same evidence (daily dimensions instead of
six-month categories; see §5), not a new calculation.

**HUMAN** — entirely user-authored: check-ins, notes, practice
interactions, stated goals. Never inferred, never overwritten by the
chart, never "corrected" toward what the chart suggests.

Every stored signal carries an explicit `source` tag (`chart` |
`self_report` | later `external`) so these two domains can never get
silently conflated — not in storage, not in a prompt, not in an analysis
later. **When they conflict, human data wins**, always, and the product
says so out loud rather than picking silently:

> "Your forecast suggested a quieter stretch, but you're telling me you
> feel unusually energized. Let's work with what you're actually
> experiencing."

This isn't a copy guideline the LLM is trusted to remember — it's
enforced the same way the reading engine already enforces "don't let the
LLM decide what's significant" (see `app/backend/reading.py`'s why-panels
and ranking): a deterministic rule in code decides which state the
practice-matching and copy-generation logic treats as authoritative, and
the LLM's job stays limited to writing the sentence, not making the call.

---

## 3. Core user journey

**Onboarding (one time).** Birth data capture (already built) → chart
computed once, cached. A short "what's currently on your mind" is
optional, not gating — someone should be able to open the app and get
value without answering a survey first.

**Daily loop (the habit the product is actually built around).**

1. Open the app → **Today** screen: a handful of plain-language lines
   describing today's climate, each with an optional "why."
2. If not already done today, a lightweight **check-in** prompt: how are
   you, what's taking up space, optional note.
3. **Regulate** surfaces one matched practice (not a menu) — chosen from
   chart-state, and from the check-in if one exists today, with an easy
   "not feeling this — show me something else" escape hatch.
4. A **Prepare nudge** appears *only* when a genuinely evidenced window
   is close enough to matter (proximity threshold, see §7) — most days
   this section simply doesn't render. No filler.
5. A quiet link out to the full **Season** reading.

**Periodic / on demand.** Season (the existing six-month reading) lives
in its own tab, regenerated every few weeks rather than daily — the
underlying evidence doesn't meaningfully change day to day, and it's
expensive to regenerate for no reason. **Journal** is the check-in
archive. **Patterns** (Learn) appears once there's enough history to say
anything honest.

---

## 4. Screens & navigation

Four tabs, mobile-first, no new visual language (existing tokens/
components extend, nothing is redesigned per your instruction):

| Tab | Purpose |
|---|---|
| **Today** | Daily Understand + check-in + Regulate + Prepare nudge. The new front door. |
| **Season** | The existing six-month reading, unchanged. The long-lens view of Prepare. |
| **Journal** | Check-in history, notes, past practice interactions. |
| **Patterns** | Learn. Hidden or shown as "not enough data yet" until there's a real sample (see §9). |

Deliberately **no separate "Practices" tab in V1.5.** Manifestation and
intervention content is surfaced *contextually* from Today and Journal,
never as a browsable library — that's precisely the "generic content
feed" shape you flagged as the thing not to become. Worth revisiting once
there's real usage data, not before.

---

## 5. Today screen: the Understand layer

**Dimensions**, replacing the six-month reading's life categories for
daily use (both read the same underlying chart data, just cut
differently — see §5.1):

- Emotional climate
- Energy
- Social energy
- Creativity
- Decision-making
- Relationships
- Rest vs. action

Each dimension gets a computed valence (e.g. *activated* vs. *quiet*,
*outward* vs. *inward*) from the same Strong/Moderate evidence the engine
already produces — this is a new **mapping layer**
(`daily_dimensions.py`, mirroring `theme_definitions.py`'s pattern: house/
planet significators, generic and chart-agnostic, not hand-tuned per
person) tuned to these seven axes instead of the six life categories.

**Not all seven are shown every day.** Forcing a line for a dimension
with no real signal is exactly the "invented texture" the reading engine
already refuses to do (see `classify_hit_strength`'s honesty about "weak"
evidence). Today only surfaces dimensions with an actual signal; if
nothing is notably active anywhere, the screen says a calm, honest
version of that ("a quiet, steady day — nothing pulling hard in any
direction") instead of manufacturing five lines of filler.

Every line carries a "why am I seeing this?" disclosure — the same
pattern already built for Season's category cards, extended here. The
astrology is always presented as symbolic framing, never causation:

> "This kind of period is traditionally read as more emotionally
> demanding. If that resonates with how you've been feeling..."

never

> "Saturn is making you feel this way."

This framing template is a shared prompt fragment, not duplicated per
feature, so Understand, Regulate, and Prepare copy all inherit it
consistently.

### 5.1 Relationship to Season

Today's dimensions and Season's six life categories are two different
*views* over the same evidence engine, not two engines. Today asks "what
does the chart suggest is active right now, cut by emotional/behavioral
axis"; Season asks "what does the chart suggest across relationships,
work, money, home, health, growth, over six months." No new astrology
gets computed for Today beyond what `theme_definitions.py`'s pattern
already generalizes — a new significator mapping, not new calculation.

---

## 6. Reflect: the check-in

Two-step, optional third step, matching your spec exactly:

1. **"How are you today?"** — single-select: Energised, Calm, Happy,
   Flat, Anxious, Emotional, Irritable, Overwhelmed, Exhausted.
2. **"What's taking up the most space?"** (optional) — single-select:
   Relationship, Work, Money, Family, Health, Myself, Something else,
   I don't know.
3. **Optional short note** (free text).

One check-in per calendar day is the canonical record (editable until
midnight, not appended-to) — this keeps the eventual Learn analysis
honest: one chart-snapshot, one reported-state, one day, no ambiguity
about which check-in a given day's chart data should be compared against.

Stored as: `{date, mood, life_area, note, chart_snapshot_ref, created_at}`.
`chart_snapshot_ref` points at that day's computed dimension read,
captured **at check-in time** — this is the single piece of plumbing that
makes Learn (§9) possible later without redesigning storage.

---

## 7. Regulate: practice matching

Deliberately **not** an LLM improvising a practice from scratch each
time. A small, explicit, auditable matching table decides the practice
*type*; the LLM only writes the *copy* for that type, grounded in both
data streams — same division of labor as Season's ranking/prose split.

**Practice types** (taxonomy, not a menu the user browses):
grounding, nervous-system regulation, breathwork, reflective journaling,
processing journaling, visualization, intention-setting, affirmation,
movement, rest/recovery, creative expression, relationship reflection,
gratitude, planning/action, exploration.

**Matching logic**, human-reported state takes priority when present:

| Reported state | Chart state | → Practice direction |
|---|---|---|
| Overwhelmed / Anxious / Emotional | (any) | Grounding, nervous-system regulation, slowing down |
| Energised / Happy | Expansive / outward | Action-oriented: planning, creative work, "is there something you've been waiting to start?" — **not** automatically calming them down |
| Flat / Exhausted | Quiet / inward | Rest, recovery, gentle reflection, explicit permission to not force momentum |
| No check-in yet | (chart only) | Chart-implied direction, framed more provisionally since the human signal is absent |
| Reported state contradicts chart | — | **Human wins.** Practice matches what they reported; copy names the mismatch instead of silently picking a side |

This table is real code (a lookup structure, testable like everything
else in `astroengine`), not a prompt asking the model to "be sensible."

---

## 8. Prepare: nudges before, not just readings after

Reuses the timeline-bucketing logic already built for Season (`_bucket_
strong_hits` in `reading.py`) but tightens it for a *proximity-triggered
nudge* rather than a full six-month bucket list:

- Only strong-tier, dated evidence creates a nudge — same rule as Season's
  timeline, no new leniency.
- A nudge fires when that evidenced window is within a configurable
  proximity (proposed default: 14 days out), once, not repeated daily
  once shown.
- Copy is preparatory, not predictive: *"you're approaching a more
  emotionally demanding stretch in five days — worth protecting some
  recovery time"* rather than any claim about what will externally
  happen.
- No nudge fires when nothing evidenced is actually close — silence is
  a valid, expected, common state here.

---

## 9. Learn: pattern recognition (architecture only, not built in V1.5)

The critical enabling piece — storing a chart snapshot alongside every
check-in (§6) — ships in V1.5. The analysis that reads that data does
not; it needs weeks of real check-ins to say anything honest, and
building it now would mean either faking results or shipping an empty
tab.

**Proposed approach, for later:** simple, transparent statistics over
paired (chart-dimension, reported-mood) days — not a black-box model.
Compare, e.g., how often "Anxious" was reported on days the engine
flagged as high-pressure vs. other days, and report the finding *with*
an explicit sample-size caveat, the same honesty pattern
`evidence_strength` already has for astrology itself.

Three valid output states, symmetric by design:

- **Correlation found** — "you tend to report more anxiety during
  periods the engine reads as high-pressure."
- **No correlation found** — "your sleep-adjacent mood reports don't
  appear to track these cycles" (this is not a failure state — it's the
  system doing its job).
- **Not enough data yet** — the honest default for most users most of
  the time early on.

The system must be structurally as ready to report the second state as
the first. This is a philosophy commitment, not just a UX nicety — it's
what keeps Aphelion from becoming confirmation-bias software.

---

## 10. Manifestation / intention

Treated as intention + attention + visualization + behavior, never as a
guarantee of external outcomes. In V1.5: a small set of practice types
(future-self visualization, morning intention, evening reflection,
personal affirmation, future-self letter), each generated as *text*,
grounded in the person's current dimensions and any stated goals — this
fits directly into the Regulate matching architecture in §7, it's not a
separate system.

**Explicitly later:** AI-generated audio recordings. V1.5 ships text the
person can read or record in their own voice; synthesized audio is a
real feature but a distinct piece of scope (voice generation, storage,
playback) that doesn't need to block this.

---

## 11. Wellness (explicitly deferred)

Per your instruction: **not built now.** The only V1.5 obligation is
architectural — keep a clean seam so it can be added later without a
redesign:

- Chart-scoring code has **no call path** into any future wellness/health
  recommendation logic, structurally, not just by convention.
- When wellness logic eventually exists, it consumes **HUMAN-domain data
  + evidence-based wellness logic only** — never chart data directly. No
  "Saturn → take magnesium" path can exist because there's no wire
  between those modules to begin with.
- Sleep, movement, nutrition, cycle tracking, wearables, habits: all
  future `source: external` signal types under the same tagging scheme
  as §2, added with explicit per-integration user consent, not in this
  phase.

---

## 12. New data this requires

V1 was stateless — compute per request, nothing persisted. This is the
first time Aphelion needs real storage, and (at least minimally) a way to
recognize the same person across visits. Proposed additions:

- **Profile** — birth data + cached natal chart (never recomputed unless
  birth data changes) + settings.
- **CheckIn** — one per day, `source: self_report` (§6).
- **DailyDimensionSnapshot** — that day's computed Understand read,
  `source: chart`, generated once per day and cached (not recomputed on
  every screen visit — keeps LLM cost sane and guarantees the chart-
  snapshot-at-checkin-time link in §6 is stable).
- **SeasonSnapshot** — the existing six-month reading, cached with a
  generation date, regenerated on a slower cadence (proposed: every 2–4
  weeks, or on demand) rather than per visit.
- **PracticeInteraction** — which practice type was shown, whether opened/
  completed, when — the log Learn eventually reads for "did this actually
  get used," separate from whether it correlates with mood.
- Lightweight **identity** (even just an email/magic-link or device-bound
  account) — the minimum needed to keep check-ins across sessions. Not
  proposing a full account system in this document; flagging that some
  form of it is now unavoidable scope, worth its own short design pass
  before V1.5 build starts.

---

## 13. What belongs in V1.5

- Today screen: computed dimension scoring (`daily_dimensions.py`, new
  significator mapping, no new astrology) + plain-language LLM
  translation, reusing the existing jargon-ban prompt pattern.
- Check-in flow (§6), stored.
- Regulate matching table (§7) + LLM-written copy per matched type.
- Prepare nudge (§8), reusing existing timeline-bucketing logic.
- Season tab = today's reading, unchanged, re-served on a slower cadence.
- Journal tab = check-in history.
- Minimal persistence + identity, sufficient to make the above possible.
- "Why am I seeing this?" extended from Season cards to Today's
  dimensions.
- Manifestation as text-only practice types inside the Regulate system
  (§10).
- The CHART/HUMAN separation (§2) and the safety framing template (§5)
  as shared, reusable code — not duplicated per feature.

## What explicitly waits

- Patterns/Learn's actual correlation surfacing (§9) — store the data
  now, build the analysis once there's a real sample.
- AI-generated audio manifestation recordings.
- Any wellness data integration (§11) — extension point only.
- Full account system polish (social login, multi-device sync, etc.).
- A dedicated, browsable Practices tab/library.
- Any visual redesign — new screens extend existing tokens/components.

---

## 14. Decisions (confirmed)

1. **Identity/persistence** — email + magic link. No password. In this
   dev environment there's no outbound email sending configured, so the
   magic-link token is returned directly in the API response / logged
   server-side rather than emailed, clearly marked as a dev-mode
   shortcut — swapping in a real mail sender later doesn't change the
   auth flow.
2. **Daily dimension mapping** — built the same way as
   `theme_definitions.py` (generic, chart-agnostic, house/planet
   significators), reviewed the same way Season was: through real output,
   not a spec doc first.
3. **Season regeneration cadence** — every 2–4 weeks, or on demand via an
   explicit refresh.
4. **Prepare nudge proximity threshold** — 14 days.

Build starts now.
