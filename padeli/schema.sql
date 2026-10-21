PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;

CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    phone TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    skill_level TEXT NOT NULL CHECK (skill_level IN ('Beginner', 'Intermediate', 'Advanced')),
    location TEXT NOT NULL DEFAULT '',
    bio TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_name ON users(name COLLATE NOCASE);
CREATE INDEX IF NOT EXISTS idx_users_skill ON users(skill_level);
CREATE INDEX IF NOT EXISTS idx_users_location ON users(location COLLATE NOCASE);

CREATE TABLE IF NOT EXISTS games (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    organizer_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    location TEXT NOT NULL,
    game_date TEXT NOT NULL,
    game_time TEXT NOT NULL,
    required_level TEXT NOT NULL CHECK (required_level IN ('Beginner', 'Intermediate', 'Advanced')),
    max_players INTEGER NOT NULL CHECK (max_players BETWEEN 2 AND 8),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (organizer_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_games_date_time ON games(game_date, game_time);
CREATE INDEX IF NOT EXISTS idx_games_level ON games(required_level);

CREATE TABLE IF NOT EXISTS game_participants (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    joined_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE (game_id, user_id)
);

CREATE INDEX IF NOT EXISTS idx_participants_user ON game_participants(user_id);

CREATE TABLE IF NOT EXISTS feedback (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id INTEGER NOT NULL,
    reviewer_id INTEGER NOT NULL,
    reviewed_user_id INTEGER NOT NULL,
    rating INTEGER NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (game_id) REFERENCES games(id) ON DELETE CASCADE,
    FOREIGN KEY (reviewer_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (reviewed_user_id) REFERENCES users(id) ON DELETE CASCADE,
    CHECK (reviewer_id <> reviewed_user_id),
    UNIQUE (game_id, reviewer_id, reviewed_user_id)
);

CREATE INDEX IF NOT EXISTS idx_feedback_reviewed ON feedback(reviewed_user_id);
