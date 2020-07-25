from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Optional, List
from uuid import UUID

from fastapi import Depends, APIRouter, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field
from config import OAUTH_SECRET_KEY, OAUTH_JWT_ALGORITHM, ACCESS_TOKEN_EXPIRE_MINUTES

fake_users_db = {
    "elvinv": {
        "username": "elvinv",
        "full_name": "Elvin Voh",
        "email": "elvinv@example.com",
        "hashed_password": "$2b$12$mNFOzbWeA9EIrTK0um5K7OlxYnRQcrB.5EtrlPFLbcRrHnF1XhPv2",
        "disabled": False,
        "permissions": ["b388caf0-baa3-4bd2-8e13-feb2fa7be097"]
    },
    "vivim": {
        "username": "vivim",
        "full_name": "Vivi Mo",
        "email": "vivim@example.com",
        "hashed_password": "$2b$12$mNFOzbWeA9EIrTK0um5K7OlxYnRQcrB.5EtrlPFLbcRrHnF1XhPv2",
        "disabled": False,
        "permissions": []
    }
}


class InitiativePermissions(Enum):
    Define = UUID("b388caf0-baa3-4bd2-8e13-feb2fa7be097")


@dataclass
class Permission:
    id: UUID
    name: str


permissions_db = [
    Permission(id="b388caf0-baa3-4bd2-8e13-feb2fa7be097", name="initiative.define")
]


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class User(BaseModel):
    username: str
    email: Optional[str] = None
    full_name: Optional[str] = None
    disabled: Optional[bool] = None
    permissions: List[UUID] = Field(default_factory=list)


class UserInDB(User):
    hashed_password: str


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

router = APIRouter()


def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_user(db, username: str):
    if username in db:
        user_dict = db[username]
        return UserInDB(**user_dict)


def authenticate_user(fake_db, username: str, password: str):
    user = get_user(fake_db, username)
    if not user:
        return False
    if not verify_password(password, user.hashed_password):
        return False
    return user


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    if expires_delta:
        expire = datetime.utcnow() + expires_delta
    else:
        expire = datetime.utcnow() + timedelta(minutes=15)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, OAUTH_SECRET_KEY, algorithm=OAUTH_JWT_ALGORITHM)
    return encoded_jwt


async def user_is_authenticated(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, OAUTH_SECRET_KEY, algorithms=[OAUTH_JWT_ALGORITHM])
        username: str = payload.get("sub")
        if username is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    user = get_user(fake_users_db, username=username)
    if user is None:
        raise credentials_exception
    return user


def user_is_authorized_for_permission(permission_id: UUID):
    if permission_id is None:
        raise ValueError(f"Missing Permission.")

    async def user_is_authorized(user: User = Depends(user_is_authenticated)):

        if not any(permission == permission_id for permission in user.permissions):

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="User does not have access."
            )

        return User

    return user_is_authorized


async def get_current_active_user(current_user: User = Depends(user_is_authenticated)):
    if current_user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return current_user


@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(form_data: OAuth2PasswordRequestForm = Depends()):
    user = authenticate_user(fake_users_db, form_data.username, form_data.password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    access_token = create_access_token(
        data={"sub": user.username}, expires_delta=access_token_expires
    )
    return {"access_token": access_token, "token_type": "bearer"}


@router.get("/users/me/", response_model=User)
async def read_users_me(current_user: User = Depends(get_current_active_user)):
    return current_user
