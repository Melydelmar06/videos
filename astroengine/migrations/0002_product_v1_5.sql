-- V1.5 product layer: identity, daily check-ins/snapshots, cached season
-- readings, practice interaction log. See PRODUCT_ARCHITECTURE.md.
--
-- CHART data (daily_dimension_snapshots, season_snapshots) and HUMAN data
-- (check_ins, practice_interactions) are kept in separate tables on
-- purpose, per PRODUCT_ARCHITECTURE.md section 2 -- never merge them into
-- one row, so no future query can accidentally treat a self-report as
-- chart-derived or vice versa.

CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE magic_link_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token TEXT NOT NULL UNIQUE,
    expires_at TEXT NOT NULL,
    used_at TEXT,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_magic_link_tokens_user ON magic_link_tokens(user_id);

-- birth_profiles predates accounts (V1 was single-profile, no auth).
-- user_id is nullable so existing rows aren't broken; going forward every
-- new profile created through the product is tied to a user.
ALTER TABLE birth_profiles ADD COLUMN user_id INTEGER REFERENCES users(id) ON DELETE CASCADE;
CREATE INDEX idx_birth_profiles_user ON birth_profiles(user_id);

-- CHART data: today's Understand dimension read. One per user per day,
-- generated once and cached (see reading engine's existing "strong
-- corroboration" honesty pattern -- source is always 'chart', never
-- touched by a check-in).
CREATE TABLE daily_dimension_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    snapshot_date TEXT NOT NULL,
    dimensions_json TEXT NOT NULL,
    generated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, snapshot_date)
);
CREATE INDEX idx_daily_dimension_snapshots_user ON daily_dimension_snapshots(user_id);

-- HUMAN data: the daily check-in. One per user per calendar day
-- (overwritable same-day, not appended). chart_snapshot_ref links to that
-- day's CHART read purely for later pattern analysis (Learn) -- it is
-- never used to override or "correct" the reported mood/life_area.
CREATE TABLE check_ins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    checkin_date TEXT NOT NULL,
    mood TEXT NOT NULL,
    life_area TEXT,
    note TEXT,
    chart_snapshot_id INTEGER REFERENCES daily_dimension_snapshots(id) ON DELETE SET NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now')),
    UNIQUE(user_id, checkin_date)
);
CREATE INDEX idx_check_ins_user ON check_ins(user_id);

-- CHART data: the existing six-month Season reading, cached so it's
-- regenerated on a slow cadence (every 2-4 weeks, or on explicit
-- refresh) rather than on every visit.
CREATE TABLE season_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    window_start TEXT NOT NULL,
    window_end TEXT NOT NULL,
    reading_json TEXT NOT NULL,
    generated_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_season_snapshots_user ON season_snapshots(user_id);

-- HUMAN data (interaction log, not a report of internal state, but still
-- user-behavior-derived rather than chart-derived): which Regulate
-- practice was shown and whether it was engaged with. Feeds Learn later;
-- never read by the chart-scoring layer.
CREATE TABLE practice_interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    interaction_date TEXT NOT NULL,
    practice_type TEXT NOT NULL,
    shown_at TEXT NOT NULL DEFAULT (datetime('now')),
    opened_at TEXT,
    completed_at TEXT
);
CREATE INDEX idx_practice_interactions_user ON practice_interactions(user_id);
