from pydantic import BaseModel


class FCMRegisterTokenBody(BaseModel):
    fid: str
    token: str


class FCMUnregisterTokenBody(BaseModel):
    fid: str
