-- создает новый профиль
INSERT INTO profiles (name, github_repo_url, is_active, port)
VALUES (COALESCE(?, NULL), COALESCE(?, NULL), COALESCE(?, NULL), COALESCE(?, NULL));
