-- создает нового пользователя
INSERT INTO users (login, hash_password)
VALUES (COALESCE(?, NULL), COALESCE(?, NULL));