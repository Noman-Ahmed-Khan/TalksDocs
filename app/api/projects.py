from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List
from app.db import crud, session, models
from app.schemas import project as project_schema
from app.dependencies import get_current_user

router = APIRouter()

@router.post("/", response_model=project_schema.Project)
def create_project(
    project_in: project_schema.ProjectCreate,
    db: Session = Depends(session.get_db),
    current_user: models.User = Depends(get_current_user)
):
    return crud.create_project(db, project=project_in, owner_id=current_user.id)

@router.get("/", response_model=List[project_schema.Project])
def read_projects(
    db: Session = Depends(session.get_db),
    current_user: models.User = Depends(get_current_user)
):
    return crud.get_projects(db, owner_id=current_user.id)

@router.get("/{id}", response_model=project_schema.Project)
def read_project(
    id: str,
    db: Session = Depends(session.get_db),
    current_user: models.User = Depends(get_current_user)
):
    project = crud.get_project(db, project_id=id, owner_id=current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
