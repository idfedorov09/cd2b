from typing import Optional

from fastapi import FastAPI, WebSocket
import uvicorn
from pydantic import BaseModel

import cd2b_api

app = FastAPI()


class ProfileRequest(BaseModel):
    name: str
    github: str
    port: int = 5613
    post_proc: Optional['bool'] = None


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
    response['profile_object'] = str(profile)
    return response


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


# Build and Run profile. If profile is running - exception
@app.websocket("/bandr")
async def bandr(profile_name: str, websocket: WebSocket):
    await websocket.accept()
    profile = await cd2b_api.get_by_name(profile_name)
    await profile.rerun(websocket=websocket)
    await websocket.close()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
