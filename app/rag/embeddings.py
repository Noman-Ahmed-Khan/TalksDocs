from langchain_google_genai import GoogleGenerativeAIEmbeddings
from app.settings import settings

def get_embeddings():
    return GoogleGenerativeAIEmbeddings(
        model=settings.EMBEDDING_MODEL,
        google_api_key=settings.GOOGLE_API_KEY
    )
