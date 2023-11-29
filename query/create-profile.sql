-- создает новый профиль
INSERT INTO profiles (name, github_repo_url, port)
VALUES (COALESCE(?, NULL), COALESCE(?, NULL), COALESCE(?, NULL));
