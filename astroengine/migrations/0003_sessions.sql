-- Session tokens issued after a magic link is consumed. Kept separate
-- from magic_link_tokens (single-use, short-lived, email-delivery-bound)
-- since a session is long-lived and reusable across requests.
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    token TEXT NOT NULL UNIQUE,
    created_at TEXT NOT NULL DEFAULT (datetime('now')),
    expires_at TEXT NOT NULL
);
CREATE INDEX idx_sessions_user ON sessions(user_id);
