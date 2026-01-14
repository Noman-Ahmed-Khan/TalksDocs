from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from sqlalchemy.orm import Session
from typing import List
import os
import shutil
import uuid
from app.db import crud, session, models
from app.schemas import document as document_schema
from app.dependencies import get_current_user
from app.settings import settings
from app.rag.loaders import DocumentLoader
from app.rag.chunking import Chunker
from app.rag.vectorstore import get_vectorstore

router = APIRouter()

@router.post("/upload", response_model=document_schema.Document)
async def upload_document(
    project_id: str = Form(...),
    file: UploadFile = File(...),
    db: Session = Depends(session.get_db),
    current_user: models.User = Depends(get_current_user)
):
    # 1. Verify project ownership
    project = crud.get_project(db, project_id=project_id, owner_id=current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # 2. Save original file
    if not os.path.exists(settings.UPLOAD_DIR):
        os.makedirs(settings.UPLOAD_DIR)
        
    file_id = str(uuid.uuid4())
    file_ext = os.path.splitext(file.filename)[1]
    file_path = os.path.join(settings.UPLOAD_DIR, f"{file_id}{file_ext}")
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # 3. Create document record in DB
    db_doc = crud.create_document(
        db, 
        filename=file.filename, 
        project_id=project_id, 
        file_path=file_path
    )

    # 4. Ingestion pipeline: Load, Chunk, Embed, Store
    try:
        # Load
        loader = DocumentLoader()
        raw_docs = loader.load(file_path)
        
        # Chunk
        chunker = Chunker()
        chunks = chunker.split_documents(raw_docs, document_id=db_doc.id)
        
        # Store in Vector DB (Embeddings are handled inside vectorstore)
        vectorstore = get_vectorstore(project_id)
        # Ensure metadata is properly formatted for Pinecone
        texts = [c.page_content for c in chunks]
        metadatas = [c.metadata for c in chunks]
        # langchain Pinecone expects 'source' in metadata often
        for m in metadatas:
            m["source"] = file.filename
            
        vectorstore.add_texts(texts=texts, metadatas=metadatas)
        
    except Exception as e:
        # Cleanup if failed
        # os.remove(file_path)
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {str(e)}")

    return db_doc

@router.get("/{project_id}", response_model=List[document_schema.Document])
def read_documents(
    project_id: str,
    db: Session = Depends(session.get_db),
    current_user: models.User = Depends(get_current_user)
):
    project = crud.get_project(db, project_id=project_id, owner_id=current_user.id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return crud.get_documents_by_project(db, project_id=project_id)
