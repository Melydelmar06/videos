CREATE TABLE birth_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    birth_date TEXT NOT NULL,
    birth_time TEXT,
    time_known INTEGER NOT NULL,
    birth_place TEXT NOT NULL,
    latitude REAL NOT NULL,
    longitude REAL NOT NULL,
    timezone_name TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE astrology_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    birth_profile_id INTEGER NOT NULL UNIQUE REFERENCES birth_profiles(id) ON DELETE CASCADE,
    zodiac_type TEXT NOT NULL,
    ayanamsha TEXT,
    house_system TEXT NOT NULL,
    node_type TEXT NOT NULL,
    rulership_scheme TEXT NOT NULL,
    aspect_set_json TEXT NOT NULL,
    orb_rules_json TEXT NOT NULL,
    timezone_policy_json TEXT NOT NULL,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    updated_at TEXT NOT NULL DEFAULT (datetime('now'))
);

CREATE TABLE natal_planets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    birth_profile_id INTEGER NOT NULL REFERENCES birth_profiles(id) ON DELETE CASCADE,
    planet TEXT NOT NULL,
    longitude REAL NOT NULL,
    sign TEXT NOT NULL,
    degree_in_sign REAL NOT NULL,
    house INTEGER,
    is_retrograde INTEGER NOT NULL,
    speed_longitude REAL NOT NULL,
    data_confidence_json TEXT NOT NULL
);
CREATE INDEX idx_natal_planets_profile ON natal_planets(birth_profile_id);

CREATE TABLE natal_houses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    birth_profile_id INTEGER NOT NULL REFERENCES birth_profiles(id) ON DELETE CASCADE,
    house_number INTEGER NOT NULL,
    longitude REAL NOT NULL,
    sign TEXT NOT NULL,
    degree_in_sign REAL NOT NULL,
    ruling_planet TEXT NOT NULL,
    data_confidence_json TEXT NOT NULL,
    UNIQUE(birth_profile_id, house_number)
);

CREATE TABLE natal_angles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    birth_profile_id INTEGER NOT NULL REFERENCES birth_profiles(id) ON DELETE CASCADE,
    name TEXT NOT NULL,
    longitude REAL NOT NULL,
    sign TEXT NOT NULL,
    degree_in_sign REAL NOT NULL,
    data_confidence_json TEXT NOT NULL,
    UNIQUE(birth_profile_id, name)
);

CREATE TABLE natal_aspects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    birth_profile_id INTEGER NOT NULL REFERENCES birth_profiles(id) ON DELETE CASCADE,
    point_a TEXT NOT NULL,
    point_b TEXT NOT NULL,
    aspect_type TEXT NOT NULL,
    exact_angle REAL NOT NULL,
    orb REAL NOT NULL,
    is_applying INTEGER NOT NULL,
    data_confidence_json TEXT NOT NULL
);
CREATE INDEX idx_natal_aspects_profile ON natal_aspects(birth_profile_id);

CREATE TABLE life_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    birth_profile_id INTEGER NOT NULL REFERENCES birth_profiles(id) ON DELETE CASCADE,
    start_date TEXT NOT NULL,
    end_date TEXT,
    category TEXT NOT NULL,
    title TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    importance INTEGER NOT NULL DEFAULT 3,
    created_at TEXT NOT NULL DEFAULT (datetime('now'))
);
CREATE INDEX idx_life_events_profile ON life_events(birth_profile_id);
