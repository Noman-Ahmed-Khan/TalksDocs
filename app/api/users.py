from fastapi import APIRouter, Depends
from app.dependencies import get_current_user
from app.db import models
from app.schemas import user as user_schema

router = APIRouter()

@router.get("/me", response_model=user_schema.User)
def read_user_me(current_user: models.User = Depends(get_current_user)):
    return current_user
