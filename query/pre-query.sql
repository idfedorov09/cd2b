-- создает БД с профилями
CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    github_repo_url TEXT,
    port INTEGER
);