import asyncio
import os
import shutil
import subprocess
from typing import Optional

import git
import requests

import cd2b_db_core


async def create_profile(
        name: str,  # имя профиля
        github: str,  # github url
        port: int = 5613,  # порт сервера
        post_proc: bool = True  # нужно ли выполнять особые действия после создания объекта
) -> Optional['Profile']:
    pre_profile = Profile(name, github, port)
    if post_proc:
        await pre_profile._Profile__post_proc()
    return pre_profile


class Profile:
    def __init__(self,
                 name: str,  # имя профиля
                 github: str,  # github url
                 port: int = 5613,  # порт сервера
                 ):
        # TODO: сделать name изменяемым
        self._name = name

        self.github = github
        self.port = port

        self.repo_name = self.github.split('/')[-1].replace('.git', '')
        self.docker_image_name = f'cd2b_{self.repo_name}_{self._name}'

        # создаем папку с пропертями если ее не существует
        create_dirs(f'./PROPERTIES/{self.docker_image_name}/')

    async def __post_proc(self):
        await self.__can_create()
        # сохраняем профиль в бдшке
        await self.save()
        await self.__clone_git_()

    # метод проверяющий профиль на валидность
    async def __can_create(self):
        self_dict_form = await self.to_dict()
        await cd2b_db_core.check_profile_data(self_dict_form)

    # создаем папку с гитхаб-репо и клонируем его
    async def __clone_git_(self):
        repo_path = f'./repos/{self.docker_image_name}/{self.repo_name}'

        if os.path.exists(repo_path):
            shutil.rmtree(repo_path)

        git.Repo.clone_from(self.github, repo_path)

    # build docker container with name self.docker_image_name
    async def build(self):
        await self.remove_image()
        await self.__clone_git_()
        await self.__apply_properties()
        build_command = (f'docker build --build-arg USER_UID=$(id -u) --build-arg USER_GID=$(id -g) '
                         f'-t {self.docker_image_name} .')
        subprocess.run(build_command, shell=True, check=True, cwd=f'./repos/{self.docker_image_name}/{self.repo_name}')

    # удаляет образ контейнера профиля
    async def remove_image(self):
        await self.stop_container()
        command = f"docker rmi {self.docker_image_name}"
        subprocess.run(command, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # запускает профиль с заданной проброской портов, то есть external_port - внешний порт приложения,
    # по которому оно будет доступно
    async def run(self, external_port: int = -1, rebuild: bool = True):
        _external_port = external_port
        if external_port == -1:
            _external_port = self.port

        await cd2b_db_core.is_valid_port(_external_port)

        if rebuild:
            await self.build()

        run_command = f"""\
docker run \
-p {_external_port}:{self.port} \
--rm \
-v $(pwd)/logs/{self.docker_image_name}/:/usr/src/app/logs \
--name {self.docker_image_name} \
-d \
{self.docker_image_name} \
"""

        # TODO: do logging
        print('run command:')
        print(run_command)
        subprocess.run(run_command, shell=True, check=True)
        pass

    # устанавливает профилю файл пропертей
    async def load_properties(self, properties_file_url: str):
        response = requests.get(properties_file_url)
        if response.status_code != 200:
            raise ConnectionError(f"Can't load property file by url {properties_file_url}")
        property_path = f'./PROPERTIES/{self.docker_image_name}/application.property'
        with open(property_path, 'wb') as file:
            file.write(response.content)

    # выгружает профиль проперти в папку с репо
    async def __apply_properties(self):
        await self.__update_property(
            'server.port',
            self.port
        )
        source_property = f'./PROPERTIES/{self.docker_image_name}/application.properties'
        destination_property = f'./repos/{self.docker_image_name}/{self.repo_name}/src/main/resources/application.properties'
        create_dirs(f'./repos/{self.docker_image_name}/{self.repo_name}/src/main/resources/')
        shutil.copy2(source_property, destination_property)

    # устанавливает порт
    async def set_port(self, new_port: int):
        # не делаем лишние походы в бд
        if self.port == new_port:
            return
        if not await cd2b_db_core.is_valid_port(new_port):
            raise ValueError(f'Port {new_port} is incorrect.')
        self.port = new_port
        await self.save()
        await self.__apply_properties()

    # меняет properties
    async def __update_property(self, property_name: str, new_value):
        properties_path = f'./PROPERTIES/{self.docker_image_name}/application.properties'
        encoding = 'utf-8'
        with open(properties_path, 'r', encoding=encoding) as file:
            lines = file.readlines()

        found = False
        for i, line in enumerate(lines):
            if line.startswith(property_name + '='):
                lines[i] = f'{property_name}={new_value}\n'
                found = True
                break

        if not found:
            lines.append(f'{property_name}={new_value}\n')

        with open(properties_path, 'w', encoding=encoding) as file:
            file.writelines(lines)

    # сохраняет профиль в бдшке
    async def save(self):
        await cd2b_db_core.save_profile(await self.to_dict())

    @property
    async def name(self) -> str:
        return self._name

    @staticmethod
    async def get_by_name(name: str, post_proc: bool = False) -> Optional['Profile']:
        profile_dict = await cd2b_db_core.get_profile(name)
        if profile_dict == {}:
            return None

        # по дефолту post_proc=False так как уже точно известно что профиль валидный и есть папка с репо
        return await Profile.from_dict(profile_dict, post_proc=post_proc)

    async def to_dict(self) -> dict:
        return {
            'name': self._name,
            'github': self.github,
            'port': self.port
        }

    @staticmethod
    async def from_dict(param: dict, post_proc: bool = True):
        return await create_profile(
            name=param.get('name'),
            github=param.get('github'),
            port=param.get('port'),
            post_proc=post_proc
        )

    # проверяет, запущен ли контейнер данного профиля
    async def is_running(self):
        command = f"docker ps | grep '{self.docker_image_name}'"
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=True)
        output, error = process.communicate()
        if process.returncode == 0:
            return output.decode('utf-8') is not None
        return False

    # останавливает контейнер профиля
    async def stop_container(self):
        if not await self.is_running():
            return
        command = f"docker stop {self.docker_image_name}"
        subprocess.run(command, shell=True, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Перезапускает контейнер, если он запущен; запускает, если выключен
    async def rerun(self, external_port: int = -1, rebuild: bool = True):
        await self.stop_container()
        await self.run(external_port=external_port, rebuild=rebuild)

    # удаляет профиль
    async def remove(self):
        await cd2b_db_core.remove_profile(self._name)
        await self.remove_image()

        # удаляем репозиторий
        repo_path = f'./repos/{self.docker_image_name}/'
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path)
        # удаляем проперти
        properties_path = f'./PROPERTIES/{self.docker_image_name}/'
        if os.path.exists(properties_path):
            shutil.rmtree(properties_path)

    def __str__(self):
        return f"Profile(name={self._name}, github={self.github}, port={self.port})"

    def __repr__(self):
        return self.__str__()


async def get_all_profiles():
    all_profiles_dicts = await cd2b_db_core.select_all_profiles()
    result = []
    for dict_profile in all_profiles_dicts:
        print(f'handle profile {dict_profile}')
        result.append(
            await Profile.from_dict(
                {
                    'name': dict_profile[1],
                    'github': dict_profile[2],
                    'port': dict_profile[3]
                }
            )
        )
    print(result)


async def remove_profile_by_name(name: str):
    await cd2b_db_core.remove_profile(name)


def create_dirs(path: str):
    directory_path = os.path.dirname(path)
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)
