-- создает БД с профилями
CREATE TABLE IF NOT EXISTS profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    github_repo_url TEXT,
    port INTEGER
);
-- создает БД с пользователями
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    login TEXT NOT NULL,
    hash_password TEXT NOT NULL
);