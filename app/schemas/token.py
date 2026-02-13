from typing import Optional
from pydantic import BaseModel

class Token(BaseModel):
    """
    Schema for the response when a user logs in.
    """
    access_token: str
    refresh_token: str  
    token_type: str


class TokenPayload(BaseModel):
    """
    Schema for the data inside the token (decoded).
    """
    sub: Optional[int] = None
    type: Optional[str] = None # "access" or "refresh"