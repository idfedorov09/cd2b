import os

from fastapi.testclient import TestClient

import main
from main import app

client = TestClient(app)


# создает тестового пользователя
def test_create_user():
    main.create_root_user(
        default_username="TEST_USER",
        default_password="12345"
    )


def test_clear_profiles():
    json_data = {
        "login": "TEST_USER",
        "password": "12345"
    }
    response = client.post(
        "/clear_profiles",
        json=json_data
    )
    assert response.status_code == 200


def test_create_profile():
    json_data = {
        "user_request": {
            "login": "TEST_USER",
            "password": "12345"
        },
        "profile_request": {
            "name": "test_profile",
            "github": "https://github.com/sno-mephi/snomephi_bot.git",
            "port": 9913
        }
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
    json_data = {
        "login": "TEST_USER",
        "password": "12345"
    }
    response = client.post(
        "/check_profile",
        params={"profile_name": "test_profile"},
        json=json_data
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
    properties_url = "https://vk.com/doc492608290_675255602?hash=Fdmi72Pc0IZcmtVrLKAx057jLqzMnpEZsHX4QSZ5IRD&dl" + \
                      "=PFivrJQ2A3UOBcNrN6UlmrNDwwIskd71DlBiizrD1Cc"
    excepted_path = "./USERS/TEST_USER/PROPERTIES/cd2b_snomephi_bot_test_profile/application.properties"
    json_data = {
        "login": "TEST_USER",
        "password": "12345"
    }
    params = {
        "profile_name": "test_profile",
        "file_url": properties_url
    }
    response = client.post(
        "/upload_prop",
        params=params,
        json=json_data
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
    json_data = {
        "login": "TEST_USER",
        "password": "12345"
    }
    params = {
        "profile_name": "test_profile",
        "port": 7779
    }
    response = client.post(
        "/set_port",
        params=params,
        json=json_data
    )

    assert response.status_code == 200
    assert response.json()['port'] == 7779


def test_all_profiles():
    json_data = {
        "login": "TEST_USER",
        "password": "12345"
    }
    response = client.post(
        "/all_profiles",
        json=json_data
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


# TODO: тест для аналогичной ws-ручки
def test_bandr_post():
    json_data = {
        "login": "TEST_USER",
        "password": "12345"
    }
    response = client.post(
        "/bandr",
        params={"profile_name": "test_profile"},
        json=json_data
    )

    assert response.status_code == 200
    assert response.json()['is_running'] == True


def test_stop_profile():
    json_data = {
        "login": "TEST_USER",
        "password": "12345"
    }
    response = client.post(
        "/stop",
        params={"profile_name": "test_profile"},
        json=json_data
    )

    assert response.status_code == 200
    assert response.json()['is_running'] == False


def test_remove():
    json_data = {
        "login": "TEST_USER",
        "password": "12345"
    }
    response = client.post(
        "/remove",
        params={"profile_name": "test_profile"},
        json=json_data
    )

    all_profiles_response = client.post(
        "/all_profiles",
        json=json_data
    )

    assert response.status_code == 200
    assert len(all_profiles_response.json()) == 0
