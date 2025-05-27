from typing import Optional

from ninja import Field, Schema


class UserOut(Schema):
    userId: str
    nickname: Optional[str] = None
    name: Optional[str]
    email: Optional[str] = None
    level: str
    profileImage: Optional[str]
    is_active: bool


class UpdateUserIn(Schema):
    nickname: Optional[str] = None
    profile_image_url: Optional[str] = Field(None, alias="profileImage")


class TokenObtainPairOutput(Schema):
    access: str
    refresh: str
