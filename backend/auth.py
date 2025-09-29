# # backend/auth.py
# from fastapi import APIRouter, Depends, HTTPException, status
# from pydantic import BaseModel, EmailStr
# from datetime import datetime, timedelta
# from jose import jwt, JWTError
# import os
# from dotenv import load_dotenv
# load_dotenv()

# from .db import AsyncSessionLocal
# from . import crud

# SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change_me_long_secret")
# ALGORITHM = "HS256"
# ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

# router = APIRouter(prefix="", tags=["auth"])

# class SignupIn(BaseModel):
#     name: str
#     email: EmailStr
#     password: str

# class TokenOut(BaseModel):
#     access_token: str
#     token_type: str = "bearer"

# class LoginIn(BaseModel):
#     email: EmailStr
#     password: str

# async def create_access_token(data: dict, expires_delta: int = ACCESS_TOKEN_EXPIRE_MINUTES):
#     to_encode = data.copy()
#     expire = datetime.utcnow() + timedelta(minutes=expires_delta)
#     to_encode.update({"exp": expire})
#     return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

# async def get_current_user(token: str = Depends(lambda: None), authorization: str = None):
#     # FastAPI way: we'll extract Bearer token from header in dependency injection below in app.
#     # This function will be used in the route dependencies via a wrapper in app.py
#     raise NotImplementedError("Use get_current_user_dependency in app.py")

# @router.post("/signup", response_model=TokenOut)
# async def signup(payload: SignupIn):
#     async with AsyncSessionLocal() as db:
#         existing = await crud.get_user_by_email(db, payload.email)
#         if existing:
#             raise HTTPException(status_code=400, detail="Email already registered")
#         user = await crud.create_user(db, payload.name, payload.email, payload.password)
#         token = await create_access_token({"sub": user.user_id})
#         return {"access_token": token, "token_type": "bearer"}

# @router.post("/login", response_model=TokenOut)
# async def login(payload: LoginIn):
#     async with AsyncSessionLocal() as db:
#         user = await crud.get_user_by_email(db, payload.email)
#         if not user or not crud.verify_password(payload.password, user.password_hash):
#             raise HTTPException(status_code=401, detail="Invalid credentials")
#         token = await create_access_token({"sub": user.user_id})
#         return {"access_token": token, "token_type": "bearer"}



# connection error update

# backend/auth.py
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta
from jose import jwt, JWTError
import os
from dotenv import load_dotenv
load_dotenv()

from sqlalchemy.ext.asyncio import AsyncSession
from .db import get_db
from . import crud

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "change_me_long_secret")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "1440"))

router = APIRouter(prefix="", tags=["auth"])

class SignupIn(BaseModel):
    name: str
    email: EmailStr
    password: str
    phone_number: str

class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"

class LoginIn(BaseModel):
    email: EmailStr
    password: str

def create_access_token(data: dict, expires_delta: int = ACCESS_TOKEN_EXPIRE_MINUTES) -> str:
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=expires_delta)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

@router.post("/signup", response_model=TokenOut)
async def signup(payload: SignupIn, db: AsyncSession = Depends(get_db)):
    existing = await crud.get_user_by_email(db, payload.email)
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    phone_number = payload.phone_number.strip()
    if not phone_number.startswith("+"):
        phone_number = f"+91{phone_number}"
        
    user = await crud.create_user(db, payload.name, payload.email, payload.password, phone_number)
    token = create_access_token({"sub": user.user_id})
    return {"access_token": token, "token_type": "bearer"}

@router.post("/login", response_model=TokenOut)
async def login(payload: LoginIn, db: AsyncSession = Depends(get_db)):
    user = await crud.get_user_by_email(db, payload.email)
    if not user or not crud.verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_access_token({"sub": user.user_id})
    return {"access_token": token, "token_type": "bearer"}

