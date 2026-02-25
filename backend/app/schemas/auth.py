from pydantic import BaseModel

class NonceResponse(BaseModel):
    nonce: str

class VerifyRequest(BaseModel):
    address: str
    signature: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
