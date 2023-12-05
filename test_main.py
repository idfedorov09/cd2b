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
    set2test()
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

    profile_info = response.json()['profile']
    assert response.status_code == 200
    assert profile_info['name'] == 'test_profile'
    assert profile_info['repo_name'] == 'snomephi_bot'
    assert profile_info['repo_uri'] == 'https://github.com/sno-mephi/snomephi_bot.git'
    assert profile_info['port'] == 9913
    assert profile_info['image_name'] == 'cd2b_snomephi_bot_test_profile'
    assert profile_info['has_properties'] == False
    assert profile_info['is_running'] == False


def test_check_profile():
    set2test()
    response = client.post(
        "/check_profile",
        params={"profile_name": "test_profile"}
    )

    profile_info = response.json()

    assert response.status_code == 200
    assert profile_info['name'] == 'test_profile'
    assert profile_info['repo_name'] == 'snomephi_bot'
    assert profile_info['repo_uri'] == 'https://github.com/sno-mephi/snomephi_bot.git'
    assert profile_info['port'] == 9913
    assert profile_info['image_name'] == 'cd2b_snomephi_bot_test_profile'
    assert profile_info['has_properties'] == False
    assert profile_info['is_running'] == False


def test_upload_properties():
    set2test()
    properties_url = "https://vk.com/doc492608290_674750778?hash=NZAYYAoCqHIAAzszC5AEnbmZKtoPRZFlhWNHfKMJZZL&dl" \
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

    profile_info = response.json()
    assert profile_info['name'] == 'test_profile'
    assert profile_info['repo_name'] == 'snomephi_bot'
    assert profile_info['repo_uri'] == 'https://github.com/sno-mephi/snomephi_bot.git'
    assert profile_info['port'] == 9913
    assert profile_info['image_name'] == 'cd2b_snomephi_bot_test_profile'
    assert profile_info['has_properties'] == True
    assert profile_info['is_running'] == False


def test_set_port():
    set2test()
    params = {
        "profile_name": "test_profile",
        "port": 7779
    }
    response = client.post(
        "/set_port",
        params=params
    )

    assert response.status_code == 200
    assert response.json()['port'] == 7779


def test_all_profiles():
    set2test()
    response = client.post(
        "/all_profiles"
    )

    assert response.status_code == 200
    assert len(response.json()) == 1

    profile_info = response.json()[0]

    assert profile_info['name'] == 'test_profile'
    assert profile_info['repo_name'] == 'snomephi_bot'
    assert profile_info['repo_uri'] == 'https://github.com/sno-mephi/snomephi_bot.git'
    assert profile_info['port'] == 7779
    assert profile_info['image_name'] == 'cd2b_snomephi_bot_test_profile'
    assert profile_info['has_properties'] == True
    assert profile_info['is_running'] == False


def test_bandr_post():
    set2test()
    response = client.post(
        "/bandr",
        params={"profile_name": "test_profile"}
    )

    assert response.status_code == 200
    assert response.json()['is_running'] == True


def test_stop_profile():
    set2test()
    response = client.post(
        "/stop",
        params={"profile_name": "test_profile"}
    )

    assert response.status_code == 200
    assert response.json()['is_running'] == False


def test_remove():
    set2test()
    response = client.post(
        "/remove",
        params={"profile_name": "test_profile"}
    )

    all_profiles_response = client.post("/all_profiles")

    assert response.status_code == 200
    assert len(all_profiles_response.json()) == 0