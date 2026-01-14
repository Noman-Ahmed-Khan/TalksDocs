from sqlalchemy.orm import Session
from app.db import models
from app.schemas import user as user_schema, project as project_schema
from app.utils.hashing import get_password_hash

def get_user_by_email(db: Session, email: str):
    return db.query(models.User).filter(models.User.email == email).first()

def create_user(db: Session, user: user_schema.UserCreate):
    hashed_password = get_password_hash(user.password)
    db_user = models.User(email=user.email, hashed_password=hashed_password)
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user

def create_project(db: Session, project: project_schema.ProjectCreate, owner_id: str):
    db_project = models.Project(**project.model_dump(), owner_id=owner_id)
    db.add(db_project)
    db.commit()
    db.refresh(db_project)
    return db_project

def get_projects(db: Session, owner_id: str):
    return db.query(models.Project).filter(models.Project.owner_id == owner_id).all()

def get_project(db: Session, project_id: str, owner_id: str):
    return db.query(models.Project).filter(
        models.Project.id == project_id,
        models.Project.owner_id == owner_id
    ).first()

def create_document(db: Session, filename: str, project_id: str, file_path: str):
    db_document = models.Document(
        filename=filename,
        project_id=project_id,
        file_path=file_path
    )
    db.add(db_document)
    db.commit()
    db.refresh(db_document)
    return db_document

def get_documents_by_project(db: Session, project_id: str):
    return db.query(models.Document).filter(models.Document.project_id == project_id).all()
