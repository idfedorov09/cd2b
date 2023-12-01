import os
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
async def process_writer(process: subprocess, websocket: Optional['WebSocket'] = None):
    output = ''
    is_gradle_downloading = False
    while True:
        if "Downloading https://services.gradle.org/" in output:
            is_gradle_downloading = True
            output = ""

        output = output+process.stderr.read(1) if is_gradle_downloading \
            else process.stderr.readline().strip().rstrip('\n')

        if output == '' and process.poll() is not None:
            break

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
