import asyncio

from fastapi.testclient import TestClient

import cd2b_api
from main import app

client = TestClient(app)


def test_create_profile():
    json_data = {
        "name": "test_profile",
        "github": 'https://github.com/sno-mephi/snomephi_bot.git',
        "port": 9913
    }

    response = client.post(
        "/create_profile",
        json=json_data
    )
    assert response.status_code == 200
