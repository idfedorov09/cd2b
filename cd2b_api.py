import os
import re
import shutil
import subprocess
from typing import Optional

import git
import requests
from fastapi import WebSocket

import cd2b_db_core
import utils


class Profile:
    def __init__(self,
                 name: str,  # имя профиля
                 github: str,  # github url
                 port: int = 5613,  # порт сервера
                 workdir: str = ".",  # рабочая директория
                 ):
        self.workdir = workdir
        # TODO: сделать name изменяемым
        self._name = name

        self.github = github
        self.port = port

        self.repo_name = self.github.split('/')[-1].replace('.git', '')
        self.docker_image_name = f'cd2b_{self.repo_name}_{self._name}'

        # создаем папку с пропертями если ее не существует
        utils.create_dirs(self.__property_folder())

    # папка содержащая проперти приложения
    def __property_folder(self) -> str:
        return utils.build_path(
            self.workdir,
            f'PROPERTIES/{self.docker_image_name}/'
        )

    # путь к проперти
    def __property_file_path(self) -> str:
        return utils.build_path(
            self.workdir,
            f'PROPERTIES/{self.docker_image_name}/application.properties'
        )

    def __repo_path_lvl1(self) -> str:
        return utils.build_path(
            self.workdir,
            f'repos/{self.docker_image_name}'
        )

    def __repo_path_lvl2(self) -> str:
        return utils.build_path(
            self.workdir,
            f'repos/{self.docker_image_name}/{self.repo_name}'
        )

    def __logs_dir(self) -> str:
        return utils.build_path(
            self.workdir,
            f'logs/{self.docker_image_name}/'
        )

    async def __post_proc(self):
        await self.__can_create()
        # сохраняем профиль в бдшке
        await self.save()
        await self.__clone_git_()
        utils.create_dirs(self.__logs_dir())

    # метод проверяющий профиль на валидность
    async def __can_create(self):
        self_dict_form = await self.to_dict()
        await cd2b_db_core.check_profile_data(self_dict_form)

    # создаем папку с гитхаб-репо и клонируем его
    async def __clone_git_(self):
        repo_path = self.__repo_path_lvl2()

        if os.path.exists(repo_path):
            shutil.rmtree(repo_path)

        git.Repo.clone_from(self.github, repo_path)

    async def has_properties(self):
        return os.path.exists(self.__property_file_path())

    # build docker container with name self.docker_image_name
    async def build(self, websocket: Optional['WebSocket'] = None):
        await self.remove_image()
        await self.__clone_git_()
        await self.__apply_properties()
        build_command = (f'docker build --build-arg USER_UID=$(id -u) --build-arg USER_GID=$(id -g) '
                         f'-t {self.docker_image_name} .')
        process = subprocess.Popen(
            build_command,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            cwd=self.__repo_path_lvl2(),
            text=True
        )

        await utils.process_writer(process, websocket)

    # удаляет образ контейнера профиля
    async def remove_image(self):
        await self.stop_container()
        command = f"docker rmi {self.docker_image_name}"
        subprocess.run(command, shell=True, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # запускает профиль с заданной проброской портов, то есть external_port - внешний порт приложения,
    # по которому оно будет доступно
    # по вебсокету отправляются логи из build
    async def run(self, external_port: int = -1, rebuild: bool = True, websocket: Optional['WebSocket'] = None):
        _external_port = external_port
        if external_port == -1:
            _external_port = self.port

        await cd2b_db_core.is_valid_port(_external_port)

        if rebuild:
            await self.build(websocket)

        run_command = f"""\
docker run \
-p {_external_port}:{self.port} \
--rm \
-v {self.__logs_dir()}:/usr/src/app/logs \
--name {self.docker_image_name} \
-d \
{self.docker_image_name} \
"""

        # TODO: do logging
        print('run command:')
        print(run_command)
        subprocess.run(run_command, shell=True, check=True)

    async def properties_content(self) -> Optional['str']:
        if not await self.has_properties():
            return None
        file_path = self.__property_file_path()
        with open(file_path, 'r') as file:
            content = file.read()
        return content

    # устанавливает профилю файл пропертей
    async def load_properties(self, properties_file_url: str):
        response = requests.get(properties_file_url)
        if response.status_code != 200:
            raise ConnectionError(f"Can't load property file by url {properties_file_url}")

        is_valid_format = await utils.is_valid_properties_file(response.text)
        if not is_valid_format:
            raise cd2b_db_core.InvalidPropertiesFormat()

        property_path = self.__property_file_path()
        with open(property_path, 'wb') as file:
            file.write(response.content)

    # выгружает профиль проперти в папку с репо
    async def __apply_properties(self):
        await self.update_property(
            'server.port',
            self.port,
            is_port=True
        )
        source_property = self.__property_file_path()
        utils.create_dirs(f'{self.__repo_path_lvl2()}/src/main/resources/')
        destination_property = f'{self.__repo_path_lvl2()}/src/main/resources/application.properties'
        shutil.copy2(source_property, destination_property)

    # устанавливает порт
    async def set_port(self, new_port: int | str):
        if not await cd2b_db_core.is_valid_port(new_port):
            raise cd2b_db_core.InvalidPortError(new_port)
        self.port = int(new_port)
        await self.save()
        await self.__apply_properties()

    # меняет properties
    async def update_property(self, property_name: str, new_value, is_port: bool = False):
        property_name = property_name.strip()
        new_value = str(new_value).strip()

        if not re.match(r'^[a-zA-Z0-9._-]+$', property_name.strip()):
            raise ValueError('Incorrect key format.')

        properties_path = self.__property_file_path()
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

        # запрещаем вручную менять порт
        if not is_port:
            await self.set_port(self.port)

    # сохраняет профиль в бдшке
    async def save(self):
        await cd2b_db_core.save_profile(await self.to_dict(), self.workdir)

    @property
    async def name(self) -> str:
        return self._name

    async def to_dict(self) -> dict:
        return {
            'name': self._name,
            'github': self.github,
            'port': self.port
        }

    @staticmethod
    async def from_dict(param: dict, workdir: str, post_proc: bool = True):
        return await create_profile(
            name=param.get('name'),
            github=param.get('github'),
            port=param.get('port'),
            post_proc=post_proc,
            workdir=workdir
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
    async def rerun(self, external_port: int = -1, rebuild: bool = True, websocket: Optional['WebSocket'] = None):
        await self.stop_container()
        await self.run(external_port=external_port, rebuild=rebuild, websocket=websocket)

    # удаляет профиль
    async def remove(self):
        await cd2b_db_core.remove_profile(self.workdir, self._name)
        await self.remove_image()

        # удаляем репозиторий
        repo_path = self.__repo_path_lvl1()
        if os.path.exists(repo_path):
            shutil.rmtree(repo_path)
        # удаляем проперти
        properties_path = self.__property_folder()
        if os.path.exists(properties_path):
            shutil.rmtree(properties_path)

    def __str__(self):
        return f"Profile(name={self._name}, github={self.github}, port={self.port})"

    def __repr__(self):
        return self.__str__()


async def get_all_profiles(workdir: str) -> list[Profile]:
    all_profiles_dicts = await cd2b_db_core.select_all_profiles(workdir)
    result: list[Profile] = []
    for dict_profile in all_profiles_dicts:
        # TODO: do logging
        print(f'getting profile {dict_profile}')
        result.append(
            await Profile.from_dict(
                {
                    'name': dict_profile[1],
                    'github': dict_profile[2],
                    'port': dict_profile[3],
                },
                post_proc=False,
                workdir=workdir
            )
        )
    return result


async def create_profile(
        name: str,  # имя профиля
        github: str,  # github url
        port: int = 5613,  # порт сервера
        workdir: str = ".",  # for ROOT
        post_proc: Optional['bool'] = None  # нужно ли выполнять особые действия после создания объекта
) -> Optional['Profile']:
    pre_profile = Profile(name=name,
                          github=github,
                          port=port,
                          workdir=workdir)

    # если профиль уже существует то не делаем post_proc
    exist_profile = await get_by_name(workdir=workdir, name=name, post_proc=False)
    if post_proc is None and exist_profile is not None:
        post_proc = False
    elif post_proc is None:
        post_proc = True

    if post_proc:
        await pre_profile._Profile__post_proc()
    return pre_profile


async def get_by_name(workdir: str, name: str, post_proc: bool = False) -> Optional['Profile']:
    profile_dict = await cd2b_db_core.get_profile(workdir=workdir, name=name)
    if profile_dict == {}:
        return None

    # по дефолту post_proc=False так как уже точно известно что профиль валидный и есть папка с репо
    return await Profile.from_dict(param=profile_dict, post_proc=post_proc, workdir=workdir)


async def remove_profile_by_name(workdir: str, name: str):
    await cd2b_db_core.remove_profile(workdir, name)
