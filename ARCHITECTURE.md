# Astrology + Numerology Data Engine — V1 Design

## What this is

A personal data engine, not an astrology app. It calculates and stores exact
chart data once, logs real-life context over time, and — on request — packages
everything relevant to a date range into a clean, structured document for an
AI (Claude) to interpret. The engine never generates prose predictions itself;
it only computes positions, finds correlations, and scores how strong the
evidence is. All narrative interpretation stays with the AI at read time.

Interface, per the requested flow:

```
My Chart → My Life → Ask About a Time Period → Generate Reading Data
```

Four screens, one SQLite file, one Python service. No dashboards, no charts-
as-wheels rendering, no multi-user auth — this is a single-user local tool.

---

## Calculation library: Swiss Ephemeris (`pyswisseph`)

**Recommendation: use `pyswisseph` directly**, the Python binding for the
Swiss Ephemeris (the same engine behind Solar Fire, Kepler, AstroGold, and
basically every professional astrology program). It's free for personal/non-
commercial use, accurate to arc-seconds (JPL DE431-derived), and gives full
control over every calculation this project needs: planetary positions,
houses (multiple systems), retrograde stations, and — critically — the custom
math for progressions, solar arcs, and solar returns, which aren't standard
"look up a position" calls.

I'd avoid outsourcing this to a hosted astrology API. Free/cheap ones are
usually natal-chart-only, rate-limited, and won't cover progressions/solar
arcs/solar returns/eclipse cross-referencing — which is most of what this
engine actually needs to do. Since this is a single user asking for
occasional date-range queries, there's no scale problem that justifies a
hosted service; a local `pyswisseph` install is simpler and gives exact
control over orbs and methods.

There's also **Kerykeion** (a Python library built on top of `pyswisseph`)
that already wraps natal chart + transit calculation in convenient objects.
It can save boilerplate for the natal chart and basic transit pieces of V1.
But it doesn't reliably cover secondary progressions, solar arc directions,
or solar return exact-moment finding — those are less common features even
among wrappers — so plan to write those directly against `pyswisseph`
regardless. Net recommendation: build the core engine on raw `pyswisseph` so
every calculation method (orbs, progression convention, return algorithm) is
explicit and consistent; optionally borrow Kerykeion's chart object as a
convenience layer if it speeds up V1, not as the source of truth.

**Numerology needs no library.** Personal Year/Month/Day and the core profile
numbers (Life Path, Expression, Soul Urge, etc.) are simple digit-sum
arithmetic on the birth date and name — implement directly, no dependency.

---

## Core data model (SQLite, single user)

```
BirthProfile
  id, name, birth_date, birth_time, birth_place,
  latitude, longitude, timezone, time_known (bool)

NatalPlanet
  planet, sign, degree_in_sign, absolute_degree,
  house, is_retrograde, speed

HouseCusp
  house_number, sign, absolute_degree, ruling_planet

NatalAngle              -- Ascendant, Midheaven, Descendant, IC
  name, sign, absolute_degree

NatalAspect
  planet_a, planet_b, aspect_type, orb, is_applying

LifeEvent
  id, start_date, end_date (nullable for single-day events),
  category,              -- relationship | career | move | fertility | financial | decision | other
  title, description,
  importance             -- 1-5, user-assigned

ThemeSignificator        -- static reference table, seeded once
  theme,                 -- e.g. "career", "children", "relationships", "relocation/visa"
  house_numbers, planets, points   -- what to check for that theme

Reading                  -- log of past queries, optional but cheap to keep
  id, query_text, date_range_start, date_range_end,
  generated_at, output_json
```

Numerology (Personal Year/Month/Day) is **derived, not stored** — it's a pure
function of birth date + target date, computed at query time.

---

## The four timing systems — computed on demand, not pre-generated forever

Precomputing transits/progressions/solar arcs for "the next 50 years" and
storing them is wasted work and storage. Instead, each is a function of
`(natal_chart, date_range) → list of hits`, run only when a query asks for a
specific window:

- **Transits** — scan the date range day-by-day (finer near exactitude) for
  transiting-planet-to-natal-point aspects within orb; record exact date,
  applying/separating, and station dates for outer planets.
- **Secondary progressions** — day-for-a-year method; compute the progressed
  chart for the query date and check progressed-planet-to-natal aspects
  (these move slowly, so check monthly resolution across the range).
- **Solar arc directions** — arc = transiting Sun's current distance from
  natal Sun; apply that arc to every natal point; check directed-to-natal
  aspects.
- **Solar returns** — find the exact annual moment (iterative search) the
  transiting Sun returns to its natal degree; build that moment's chart for
  any year touching the query range.
- **Eclipses & lunations** — a small static almanac table (global, not user-
  specific) of eclipse/New/Full Moon dates and degrees, cross-referenced
  against natal points for hits within orb.

Each hit is stored transiently as part of a query's output (in `Reading.output_json`
if you want history), not as a permanently maintained table.

---

## The important part: evidence strength, not invented meaning

For a theme (e.g. "children/motherhood") and a date range, the engine:

1. Looks up that theme's significators (`ThemeSignificator` — e.g. 5th house
   cusp/ruler, Moon, Venus, Jupiter for fertility/children).
2. Pulls every hit across all five systems above that touches one of those
   significators inside the date range.
3. Scores each hit, then classifies:

| Tier | Criteria |
|---|---|
| **Strong** | Exact hit (orb < 1°) on a hard aspect (conjunction/square/opposition) to an angle or luminary, from a slow/outer planet or a directed/progressed point — **and** corroborated by a second, independent system in the same window |
| **Moderate** | Single-system exact hit, or multiple systems with wider orbs (1–3°) |
| **Weak / background** | Minor aspects, wide orbs (3–6°), fast-planet-only transits (Moon/Mercury) unless triggering an exact natal point, or sign-based symbolism with no aspect |

The engine never merges these into "this means X will happen." It just
outputs the tiered evidence and lets the corroboration (or lack of it) speak
for itself. If a theme has only weak hits in a window, the output should say
so explicitly rather than stretching for a Strong-sounding narrative — this
is the mechanism that stops the AI layer from inventing predictions.

---

## Output packet handed to the AI

One JSON document per query — this is the actual product of "Generate
Reading Data":

```json
{
  "query": {
    "question": "What does September–October 2026 look like for my visa?",
    "date_range": {"start": "2026-09-01", "end": "2026-10-31"},
    "relevant_theme_guess": "relocation/visa"
  },
  "natal_chart_summary": {
    "angles": {"ascendant": "...", "midheaven": "..."},
    "planets": [{"name": "Sun", "sign": "...", "degree": 23.4, "house": 7, "retrograde": false}, "..."],
    "houses": ["..."],
    "major_aspects": ["..."]
  },
  "numerology": {
    "personal_year": 5,
    "personal_month": 3,
    "personal_day": 8
  },
  "life_context": [
    {"date": "2026-06-01", "category": "career", "title": "Started visa sponsorship process", "importance": 4}
  ],
  "timing_evidence": {
    "strong": [
      {"system": "solar_arc", "date": "2026-09-14", "aspect": "SA Jupiter conjunct natal MC", "orb": 0.3, "corroborated_by": ["transit"]}
    ],
    "moderate": ["..."],
    "weak": ["..."]
  },
  "theme_analysis": {
    "theme": "relocation/visa",
    "significators_checked": ["9th house", "9th house ruler", "MC", "Jupiter"],
    "convergence_note": "2 independent systems align on Sep 12-16; no other window in range shows comparable convergence"
  },
  "interpretation_guardrails": [
    "Only Strong and Moderate evidence should drive specific predictions.",
    "Weak evidence may be mentioned as minor color only, never as a standalone prediction.",
    "Do not infer outcomes (approval/denial) — only timing and thematic activation."
  ]
}
```

This is the whole contract with the AI layer: the engine hands over facts and
tiered evidence, the guardrails block it from over-reading weak symbolism,
and all interpretation/prose happens outside this engine (e.g. by pasting
this JSON into a Claude conversation, or calling the API with it as context).

---

## V1 scope (build this, nothing more)

1. Birth data input → natal chart calculation → store in SQLite.
2. Numerology profile calculation (on demand).
3. Life event log (simple CRUD, four fields: date(s), category, text, importance).
4. Date-range query → run the five timing systems → tier the evidence →
   emit the JSON packet above.
5. Minimal UI: four screens matching the stated flow. A local single-page
   app or even a CLI is enough — no chart wheel graphics, no multi-user, no
   auth.

Explicitly **not** V1: relocation/astrocartography, synastry/composite
charts with other people, chart-wheel rendering, harmonic/midpoint
techniques, a hosted multi-user backend. These can layer on later without
changing the core schema.
