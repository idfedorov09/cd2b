from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


# устанавливает тестовое окружение для тестирования
def set2test():
    response = client.post(
        "/set_env_path",
        params={"env_path": "./test_env/"}
    )
    return response


def test_set_env():
    response = set2test()
    assert response.status_code == 200


def test_create_profile():
    set2test()
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
