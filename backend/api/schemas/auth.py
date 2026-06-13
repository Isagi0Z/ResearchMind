from pydantic import BaseModel, EmailStr

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str

class UserLogin(BaseModel):
    username: str
    password: str

class UserRegister(BaseModel):
    email: EmailStr
    username: str
    password: str
