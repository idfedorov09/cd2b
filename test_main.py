import os

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


def clear_test_env():
    response = client.post(
        "/clear_env",
    )
    return response


# Полностью подготоваливает тестовое окружение, очищая его
def prepare_test_env():
    set2test()
    clear_test_env()


def test_set_env():
    response = set2test()
    assert response.status_code == 200


def test_clear_env():
    response = clear_test_env()
    assert response.status_code == 200


def test_create_profile():
    prepare_test_env()
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


def test_upload_properties():
    properties_url = "https://vk.com/doc492608290_674750778?hash=NZAYYAoCqHIAAzszC5AEnbmZKtoPRZFlhWNHfKMJZZL&dl"\
                      "=Kt0ftKXgFnOjlttHiEbYxZSzTmHHaPP0t4a219pdmDw"
    excepted_path = "./test_env/PROPERTIES/cd2b_snomephi_bot_test_profile/application.properties"
    params = {
        "profile_name": "test_profile",
        "file_url": properties_url
    }
    response = client.post(
        "/upload_prop",
        params=params
    )
    assert response.status_code == 200
    assert os.path.exists(excepted_path)
