-- создает БД с профилями
CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    github_repo_url TEXT,
    is_active INTEGER, -- 0 false, 1 true
    port INTEGER
);