from typing import Optional

from fastapi import FastAPI, WebSocket, HTTPException
import uvicorn
from pydantic import BaseModel

import cd2b_api

app = FastAPI()


class ProfileRequest(BaseModel):
    name: str
    github: str
    port: int = 5613
    post_proc: Optional['bool'] = None


async def profile_response(profile: cd2b_api.Profile):
    return {
        "name": await profile.name,
        "repo_name": profile.repo_name,
        "repo_uri": profile.github,
        "port": profile.port,
        "image_name": profile.docker_image_name,
        "is_running": await profile.is_running()
    }


@app.post("/create_profile")
async def create_profile(profile_request: ProfileRequest):
    response = {'message': "Profile created successfully."}
    if await cd2b_api.get_by_name(profile_request.name) is not None:
        response['message'] = (f'I am not creating a new profile, '
                               f'there is already a profile with name=\'{profile_request.name}\'')
    profile = await cd2b_api.create_profile(
        profile_request.name,
        profile_request.github,
        profile_request.port,
        profile_request.post_proc
    )
    response['profile'] = await profile_response(profile)
    return response


# Возвращает инфу по профилю с именем profile_name
@app.post("/check_profile")
async def check_profile(profile_name: str):
    profile = await cd2b_api.get_by_name(profile_name)
    return await profile_response(profile)


@app.post("/set_env_path")
async def set_env_path(env_path: str):
    await cd2b_api.set_workdir(env_path)


@app.post("/clear_env")
async def clear_env():
    profiles = await cd2b_api.get_all_profiles()
    for profile in profiles:
        await profile.remove()


@app.post("/upload_prop")
async def upload_prop(profile_name: str, file_url: str):
    profile = await cd2b_api.get_by_name(profile_name)
    await profile.load_properties(file_url)
    return await profile_response(profile)


# Build and Run profile. If profile is running - exception
# по сокету передает логи. если не нужны - есть аналогичный post-метод
@app.websocket("/bandr")
async def bandr_ws(profile_name: str, websocket: WebSocket, external_port: int = -1, rebuild: bool = True):
    await websocket.accept()
    profile = await cd2b_api.get_by_name(profile_name)

    if profile is None:
        error_msg = f'The profile {profile_name} does not exist.'
        await websocket.close(1001, error_msg)
        return

    if await profile.is_running():
        error_msg = f'The profile {profile_name} is already running.'
        await websocket.close(1001, error_msg)
        return

    await profile.run(
        websocket=websocket,
        external_port=external_port,
        rebuild=rebuild
    )
    await websocket.close(1000, 'ok')


# Аналог вебсокета bandr, без вывода инфы о билде. Ответ возвращается после запуска образа
@app.post("/bandr")
async def bandr_post(profile_name: str, external_port: int = -1, rebuild: bool = True):
    profile = await cd2b_api.get_by_name(profile_name)
    if profile is None:
        error_msg = f'The profile {profile_name} does not exist.'
        raise HTTPException(status_code=400, detail=error_msg)

    if await profile.is_running():
        error_msg = f'The profile {profile_name} is already running.'
        raise HTTPException(status_code=400, detail=error_msg)

    await profile.run(
        external_port=external_port,
        rebuild=rebuild
    )
    return await profile_response(profile)


# Устанавливает профилю с именем profile_name порт port
@app.post("/set_port")
async def set_port(profile_name: str, port: int | str):
    new_port = int(port)
    profile = await cd2b_api.get_by_name(profile_name)
    await profile.set_port(new_port)
    return await profile_response(profile)


@app.post("/stop")
async def stop_profile(profile_name: str):
    profile = await cd2b_api.get_by_name(profile_name)
    if profile is None:
        error_msg = f'The profile {profile_name} does not exist.'
        raise HTTPException(status_code=400, detail=error_msg)
    await profile.stop_container()
    return await profile_response(profile)


@app.post("/remove")
async def stop_profile(profile_name: str):
    profile = await cd2b_api.get_by_name(profile_name)
    if profile is None:
        error_msg = f'The profile {profile_name} does not exist.'
        raise HTTPException(status_code=400, detail=error_msg)
    await profile.remove()


@app.post("/all_profiles")
async def all_profiles():
    profiles = await cd2b_api.get_all_profiles()
    response = []
    for profile in profiles:
        response.append(await profile_response(profile))
    return response


# Build and Run profile. If profile is running - stop one and run again
# по сокету передает логи. если не нужны - есть аналогичный post-метод
@app.websocket("/rerun")
async def rerun_ws(profile_name: str, websocket: WebSocket, external_port: int = -1, rebuild: bool = True):
    await websocket.accept()
    profile = await cd2b_api.get_by_name(profile_name)

    if profile is None:
        error_msg = f'The profile {profile_name} does not exist.'
        await websocket.close(1001, error_msg)
        return

    if await profile.is_running():
        error_msg = f'The profile {profile_name} is already running.'
        await websocket.close(1001, error_msg)
        return

    await profile.rerun(
        websocket=websocket,
        external_port=external_port,
        rebuild=rebuild
    )
    await websocket.close(1000, 'ok')


# Аналог вебсокета rerun, без вывода инфы о билде. Ответ возвращается после запуска образа
@app.post("/rerun")
async def rerun_post(profile_name: str, external_port: int = -1, rebuild: bool = True):
    profile = await cd2b_api.get_by_name(profile_name)
    if profile is None:
        error_msg = f'The profile {profile_name} does not exist.'
        raise HTTPException(status_code=400, detail=error_msg)

    if await profile.is_running():
        error_msg = f'The profile {profile_name} is already running.'
        raise HTTPException(status_code=400, detail=error_msg)

    await profile.rerun(
        external_port=external_port,
        rebuild=rebuild
    )
    return await profile_response(profile)


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)
