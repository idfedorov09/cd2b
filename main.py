import asyncio
import os
from typing import Optional, Annotated

from fastapi import FastAPI, WebSocket, HTTPException, Request, Depends
import uvicorn
from pydantic import BaseModel
from starlette import status
from starlette.responses import FileResponse, HTMLResponse
from starlette.templating import Jinja2Templates

import cd2b_api
import cd2b_auth_core
import utils
from cd2b_auth_core import User
from cd2b_db_core import InvalidPortError, InvalidPropertiesFormat

app = FastAPI()
templates = Jinja2Templates(directory="templates")


class ProfileRequest(BaseModel):
    name: str
    github: str
    port: int = 5613
    post_proc: Optional['bool'] = None


class UserRequest(BaseModel):
    login: str
    password: str


async def auth_validation(user_request: UserRequest) -> User:
    user = User(user_request.login, user_request.password)
    await cd2b_auth_core.auth_validation(user)
    return User(user_request.login, user_request.password)


async def ws_auth_validation(login: str, password: str) -> User:
    return await auth_validation(UserRequest(login=login, password=password))


async def get_profile_with_auth(profile_name: str, user_request: UserRequest) -> cd2b_api.Profile:
    user = await auth_validation(user_request)
    profile = await cd2b_api.get_by_name(workdir=user.workdir, name=profile_name)
    if profile is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Profile not found"
        )
    return profile


# Контракт на профиль
async def profile_response(profile: cd2b_api.Profile):
    return {
        "name": await profile.name,
        "repo_name": profile.repo_name,
        "repo_uri": profile.github,
        "port": profile.port,
        "image_name": profile.docker_image_name,
        "has_properties": await profile.has_properties(),
        "properties_content": await profile.properties_content(),
        "is_running": await profile.is_running()
    }


@app.post("/create_profile")
async def create_profile(
        profile_request: ProfileRequest,
        user: User = Depends(auth_validation)
):
    response = {'message': "Profile created successfully."}
    if await cd2b_api.get_by_name(workdir=user.workdir, name=profile_request.name) is not None:
        response['message'] = (f'I am not creating a new profile, '
                               f'there is already a profile with name=\'{profile_request.name}\'')
    profile = await cd2b_api.create_profile(
        name=profile_request.name,
        github=profile_request.github,
        port=profile_request.port,
        workdir=user.workdir,
        post_proc=profile_request.post_proc
    )
    response['profile'] = await profile_response(profile)
    return response


# Возвращает инфу по профилю с именем profile_name
@app.post("/check_profile")
async def check_profile(
        profile: cd2b_api.Profile = Depends(get_profile_with_auth)
):
    return await profile_response(profile)


@app.post("/clear_profiles")
async def clear_profiles(
        user: User = Depends(auth_validation)
):
    # profiles = await cd2b_api.get_all_profiles(workdir=user.workdir)
    # for profile in profiles:
    #     await profile.remove()
    pass


@app.post("/upload_prop")
async def upload_prop(
        file_url: str,
        profile: cd2b_api.Profile = Depends(get_profile_with_auth)
):
    try:
        await profile.load_properties(file_url)
    except InvalidPropertiesFormat as e:
        HTTPException(status_code=400, detail=e.msg)
    return await profile_response(profile)


# TODO: дибильный способ аутентификации, переделать под JWT
# Build and Run profile. If profile is running - exception
# по сокету передает логи. если не нужны - есть аналогичный post-метод
@app.websocket("/bandr")
async def bandr_ws(
        profile_name: str,
        websocket: WebSocket,
        external_port: int = -1,
        rebuild: bool = True,
        user: User = Depends(ws_auth_validation)
):
    await websocket.accept()
    profile = await cd2b_api.get_by_name(workdir=user.workdir, name=profile_name)

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
async def bandr_post(
        external_port: int = -1,
        rebuild: bool = True,
        profile: cd2b_api.Profile = Depends(get_profile_with_auth)
):
    if await profile.is_running():
        error_msg = f"The profile '{await profile.name}' is already running."
        raise HTTPException(status_code=400, detail=error_msg)

    await profile.run(
        external_port=external_port,
        rebuild=rebuild
    )
    return await profile_response(profile)


# Устанавливает профилю с именем profile_name порт port
@app.post("/set_port")
async def set_port(
        port: int | str,
        profile: cd2b_api.Profile = Depends(get_profile_with_auth)
):
    try:
        await profile.set_port(port)
    except InvalidPortError as e:
        raise HTTPException(status_code=400, detail=e.msg)
    return await profile_response(profile)


@app.post("/stop")
async def stop_profile(
        profile: cd2b_api.Profile = Depends(get_profile_with_auth)
):
    await profile.stop_container()
    return await profile_response(profile)


@app.post("/remove")
async def stop_profile(
        profile: cd2b_api.Profile = Depends(get_profile_with_auth)
):
    await profile.remove()


@app.post("/all_profiles")
async def all_profiles(
        user: User = Depends(auth_validation)
):
    profiles = await cd2b_api.get_all_profiles(user.workdir)
    response = []
    for profile in profiles:
        response.append(await profile_response(profile))
    return response


# Build and Run profile. If profile is running - stop one and run again
# по сокету передает логи. если не нужны - есть аналогичный post-метод
# rebuild - сделать клон перед тем как запустить
@app.websocket("/rerun")
async def rerun_ws(
        profile_name: str,
        websocket: WebSocket,
        external_port: int = -1,
        rebuild: bool = True,
        user: User = Depends(ws_auth_validation)
):
    await websocket.accept()
    profile = await cd2b_api.get_by_name(workdir=user.workdir, name=profile_name)

    if profile is None:
        error_msg = f'The profile {profile_name} does not exist.'
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
async def rerun_post(
        external_port: int = -1,
        rebuild: bool = True,
        profile: cd2b_api.Profile = Depends(get_profile_with_auth)
):
    await profile.rerun(
        external_port=external_port,
        rebuild=rebuild
    )
    return await profile_response(profile)


async def is_inside_logs(path):
    in_path = os.path.abspath('./USERS')
    absolute_path = os.path.abspath(path)
    return absolute_path.startswith(in_path)


# TODO: сделать авторизацию (думаю, просто по токену, чтобы без лишних движений смотреть логи по url)
# TODO: нормальный защищенный просмотр логов
@app.get("/logs/{files_path:path}")
async def list_files(
        request: Request,
        files_path: str
):
    full_path = os.path.join(f"./USERS/", files_path)
    if not await is_inside_logs(full_path):
        return HTMLResponse(
            content=f'403, access denied: {request.url._url}',
            status_code=403
        )

    if os.path.isdir(full_path):
        files = os.listdir(full_path)
        files_paths = sorted([os.path.join(f"{request.url._url}", f) for f in files])
        return templates.TemplateResponse(
            "index.html", {"request": request, "files": files_paths}
        )
    elif os.path.isfile(full_path):
        return FileResponse(full_path)
    else:
        return HTMLResponse(
            content=f'404, not found: {request.url._url}',
            status_code=404
        )


# ручка меняющая поле пропертей
# если такого поля нет - добавляется новое
@app.post("/change_properties_field")
async def change_properties_field(
        key: str,
        value: str,
        profile: cd2b_api.Profile = Depends(get_profile_with_auth)
):
    await profile.update_property(key, value)
    return await profile_response(profile)


# TODO: do logs
# TODO: add password change feature
def create_root_user(
    default_username: str = "ROOT",
    default_password: str = "12345"
):
    try:
        asyncio.run(cd2b_auth_core.create_user(User(login=default_username, password=default_password)))
        print(f"'{default_username}' password={default_password}")
    except Exception:
        print("Don't create default user.")


if __name__ == "__main__":
    create_root_user()
    uvicorn.run(app, host="0.0.0.0", port=8000)
