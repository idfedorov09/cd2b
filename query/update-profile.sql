UPDATE profiles
SET name = ?,
    github_repo_url = ?,
    is_active = ?,
    port = ?
WHERE name = ?;
