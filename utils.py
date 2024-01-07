import os
import re
import subprocess
from typing import Optional

from fastapi import WebSocket


def create_dirs(path: str):
    directory_path = os.path.dirname(path)
    if not os.path.isfile(path):
        directory_path = path
    if not os.path.exists(directory_path):
        os.makedirs(directory_path)


def build_path(path1: str, path2: str) -> str:
    return os.path.join(
        path1,
        path2
    ).rstrip('/')


# Вспомогательный метод, отправляющий по вебсокету результат билда контейнера
# TODO: обработка ошибок
# TODO: возможно стоит читать посимвольно и проверять на новую строку? Тогда эта штука будет работать не только в случае с gradle
async def process_writer(process, websocket: Optional['WebSocket'] = None):
    output = ''
    is_gradle_downloading = False
    while process.returncode is None:
        if "Downloading https://services.gradle.org/" in output:
            is_gradle_downloading = True
            output = ""

        output = output + (await process.stderr.read(1)).decode() if is_gradle_downloading \
            else (await process.stderr.readline()).decode().strip().rstrip('\n')

        if output:
            if websocket is not None:
                await websocket.send_json(
                    {
                        "message": output,
                        "is_new_line": not is_gradle_downloading
                    }
                )
            print(output)

        if is_gradle_downloading and "100%" in output:
            is_gradle_downloading = False

        if process.stdout.at_eof() and process.stderr.at_eof():
            break


async def is_valid_properties_file(properties_content: str) -> bool:
    file_content = properties_content.split('\n')
    for line in file_content:
        if line.strip().startswith('#') or line.strip() == '':
            continue
        parts = line.split('=')
        if len(parts) != 2:
            return False
        key, value = parts
        if not re.match(r'^[a-zA-Z0-9._-]+$', key.strip()):
            return False
    return True

