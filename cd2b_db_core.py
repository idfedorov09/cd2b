import os
import re

import aiosqlite
import requests

import utils

QUERIES_PATH = './query'
DATABASE_FILE = 'cd2b_profiles.db'


# TODO: вынести исключения в отдельный модуль
class InvalidPortError(Exception):
    """Исключение для случаев, когда порт недействителен."""

    def __init__(self, port):
        self.port = port
        self.msg = f"Incorrect port {port}. Port is an Integer by segment [1; 65535]"
        super().__init__(self.msg)


class InvalidPropertiesFormat(Exception):
    """Исключение для случаев, когда application.properties имеет неверный формат"""

    def __init__(self):
        self.msg = "Incorrect properties file format."
        super().__init__(self.msg)


# БД профилей хранится в workdir/DATABASE_FILE
async def db_path(workdir: str):
    utils.create_dirs(os.path.join(workdir))
    return os.path.join(workdir, DATABASE_FILE)


# Выполняет запросы из .sql файлов. filename - название файла, без указания пути
# Без пре-запроса
async def execute_queries_with_no_prequery(filename: str, workdir: str, *params) -> list:
    filename = f'{QUERIES_PATH}/{filename}'
    with open(filename, 'r') as file:
        queries = file.read().split(';')[:-1]

    results = []
    async with aiosqlite.connect(await db_path(workdir)) as db:
        for query in queries:
            query = query.strip()
            if 'select' in query.lower():
                cursor = await db.execute(query, params)
                result = await cursor.fetchall()
                results.append(result)
                await cursor.close()
            else:
                await db.execute(query, params)
                await db.commit()
    return results


# Выполняет запрос из файла с пре-запросом
async def execute_queries(filename: str, workdir: str, *params):
    await execute_queries_with_no_prequery('pre-query.sql', workdir)
    return await execute_queries_with_no_prequery(filename, workdir, *params)


# Дропает бдшку
async def drop_profiles(workdir: str):
    async with aiosqlite.connect(await db_path(workdir)) as db:
        await db.execute(f'DROP TABLE profiles')


async def remove_profile(workdir: str, name: str):
    await execute_queries('remove-profile.sql', workdir, name)


# Возвращает все профили
async def select_all_profiles(workdir: str):
    await execute_queries_with_no_prequery('pre-query.sql', workdir)
    async with aiosqlite.connect(await db_path(workdir)) as db:
        cursor = await db.execute(f'SELECT * FROM profiles')
        rows = await cursor.fetchall()
        await cursor.close()
        return rows


# Возвращает профиль по имени
async def get_profile(workdir: str, name: str) -> dict:
    query_res = (await execute_queries('get_profile.sql', workdir, name))[0]
    if len(query_res) == 0:
        return {}
    profile_db = query_res[0]
    return {
        'name': profile_db[1],
        'github': profile_db[2],
        'port': profile_db[3]
    }


async def create_profile(profile_data: dict, workdir: str):
    # профили только с уникальными именами
    if await get_profile(workdir, profile_data.get('name')) != {}:
        raise ValueError(
            f'Profile with name \'{profile_data.get("name")}\' already exists.'
        )
    await check_profile_data(profile_data)

    await execute_queries(
        'create-profile.sql',
        workdir,
        profile_data.get('name'),
        profile_data.get('github'),
        profile_data.get('port')
    )


# проверка доступности гитхаб репозитория
async def check_github_repository(url: str):
    try:
        response = requests.get(url)
        response.raise_for_status()
        return True
    except requests.exceptions.RequestException as _:
        return False


async def is_valid_port(port: any) -> bool:
    try:
        port = int(port)
        return 1 <= port <= 65535
    except ValueError:
        return False


# Проверяет, подходит ли profile_data для добавления в таблицу.
# Если нет - выбрасывает Value Error с описанием ошибки
# Если да - ничего не делает
async def check_profile_data(profile_data: dict):
    name = profile_data.get('name')
    github_url = profile_data.get('github')
    port = profile_data.get('port')

    # имя не должно быть пусто и обязательно должно удовлетворять формату
    if name is None:
        raise ValueError("'name' is needed to create profile.")
    if not re.match(r'^[a-zA-Z_][a-zA-Z0-9_]{0,61}$', name):
        raise ValueError(
            "The name must consist of Latin letters, numbers, and underscores, "
            "and can be up to 63 characters in length."
        )

    # корректность url репозитория
    if (
            github_url is not None
            and not
            re.match(r'^https:\/\/github\.com\/[a-zA-Z0-9_.-]+\/[a-zA-Z0-9_.-]+\.git$', github_url)
    ):
        raise ValueError("Incorrect Github url.")
    # чекаем доступность репозитория, работаем только с доступными
    if (
            github_url is not None
            and
            not await check_github_repository(github_url)
    ):
        raise ValueError(
            f"Can't get data for github: {github_url}. Check repository visibility or your internet connection."
        )

    # проверяем корректность порта
    if port is not None and not await is_valid_port(port):
        raise InvalidPortError(port)


# Обновляет профиль с именем updated_profile['name']
async def update_profile(updated_profile: dict, workdir: str):
    # проверяем данные
    await check_profile_data(updated_profile)

    name = updated_profile.get('name')
    existing_profile = await get_profile(name=name, workdir=workdir)
    if existing_profile == {}:
        raise ValueError(f"Profile with name '{name}' does not exist.")

    await execute_queries(
        'update-profile.sql',
        workdir,
        name,
        updated_profile.get('github'),
        updated_profile.get('port'),
        name
    )


# Создает новую запись, если такой нет;
# если сущестувет - обновляет существующую
async def save_profile(profile_data: dict, workdir: str):
    name = profile_data.get('name')
    db_profile = await get_profile(workdir, name)
    if db_profile == {}:
        await create_profile(profile_data, workdir)
    else:
        await update_profile(profile_data, workdir)
