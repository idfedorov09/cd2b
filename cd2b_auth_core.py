from typing import Optional

from fastapi import HTTPException
from starlette import status

from cd2b_db_core import execute_queries_with_no_prequery
import hashlib


class User:
    def __init__(self,
                 login,
                 password):
        # login совпадает с workdir; в бд login - уникальные
        self.login = login
        self.hash_password = self.get_hash_password(password)
        self.workdir = f'./USERS/{login}'

    @staticmethod
    def get_hash_password(password: str) -> str:
        return hashlib.md5(f'cd2b_{password}'.encode()).hexdigest()


# выполняем пользовательские запросы
async def execute_user_queries(filename: str, *params):
    await execute_queries_with_no_prequery('pre-query.sql', ".")
    return await execute_queries_with_no_prequery(filename, ".", *params)


# Авторизация
async def auth_validation(user: User) -> Optional['User']:
    query_res = (await execute_user_queries('get_user.sql', user.login))[0]
    exception = HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if len(query_res) == 0:
        raise exception
    profile_db = query_res[0]
    if user.hash_password != profile_db[2]:
        raise exception
    return user


# Проверяет существует ли пользователь с таким логином
async def is_user_exist(login: str) -> bool:
    query_res = (await execute_user_queries('get_user.sql', login))[0]
    return len(query_res) != 0


async def create_user(user: User):
    # профили только с уникальными именами
    if await is_user_exist(user.login):
        raise ValueError(
            f'User with login \'{user.login}\' already exists.'
        )

    await execute_user_queries(
        'create-user.sql',
        user.login,
        user.hash_password
    )

    return user
