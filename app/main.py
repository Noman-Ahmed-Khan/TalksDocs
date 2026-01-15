from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import auth, users, projects, documents, query, health
from app.db.session import engine, Base, SessionLocal
from app.db import crud
from app.settings import settings

# Create database tables
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    openapi_url=f"{settings.API_V1_STR}/openapi.json"
)

@app.on_event("startup")
async def startup_event():
    # Cleanup deactivated users
    db = SessionLocal()
    try:
        crud.cleanup_deactivated_users(db)
    finally:
        db.close()

# Set up CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix=f"{settings.API_V1_STR}/auth", tags=["auth"])
app.include_router(users.router, prefix=f"{settings.API_V1_STR}/users", tags=["users"])
app.include_router(projects.router, prefix=f"{settings.API_V1_STR}/projects", tags=["projects"])
app.include_router(documents.router, prefix=f"{settings.API_V1_STR}/documents", tags=["documents"])
app.include_router(query.router, prefix=f"{settings.API_V1_STR}/query", tags=["query"])
app.include_router(health.router, prefix="/health", tags=["health"])

@app.get("/")
def root():
    return {"message": "Welcome to Living Docs API"}
