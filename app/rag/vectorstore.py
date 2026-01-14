from pinecone import Pinecone
from langchain_community.vectorstores import Pinecone as LangChainPinecone
from app.settings import settings
from .embeddings import get_embeddings

def get_vectorstore(project_id: str):
    pc = Pinecone(api_key=settings.PINECONE_API_KEY)
    embeddings = get_embeddings()
    
    # Use the specific index
    index = pc.Index(settings.PINECONE_INDEX_NAME)
    
    vectorstore = LangChainPinecone(
        index, 
        embeddings.embed_query, 
        "text", 
        namespace=project_id
    )
    return vectorstore
