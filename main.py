from typing import Optional

from fastapi import FastAPI
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
    if await cd2b_api.Profile.get_by_name(profile_request.name) is not None:
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


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
