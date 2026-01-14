from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.db import crud, session, models
from app.schemas import query as query_schema
from app.dependencies import get_current_user
from app.rag.qa import RAGQueryEngine

router = APIRouter()

@router.post("/", response_model=query_schema.QueryResponse)
async def query_documents(
    query_in: query_schema.QueryRequest,
    db: Session = Depends(session.get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. Verify project ownership
    project = crud.get_project(db, project_id=query_in.project_id, owner_id=current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # 2. Initialize RAG engine for this project
    engine = RAGQueryEngine(project_id=query_in.project_id)
    
    # 3. Perform query
    try:
        response = await engine.query(query_in.question)
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
