from typing import List, Dict, Any
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain.chains import LLMChain
from .vectorstore import get_vectorstore
from .prompts import RAG_PROMPT
from app.settings import settings
from app.schemas.query import QueryResponse, Citation

class RAGQueryEngine:
    def __init__(self, project_id: str):
        self.project_id = project_id
        self.vectorstore = get_vectorstore(project_id)
        self.llm = ChatGoogleGenerativeAI(
            model=settings.GEMINI_MODEL,
            google_api_key=settings.GOOGLE_API_KEY,
            temperature=0
        )
        self.chain = LLMChain(llm=self.llm, prompt=RAG_PROMPT)

    async def query(self, question: str) -> QueryResponse:
        # 1. Retrieve relevant chunks
        docs = self.vectorstore.similarity_search(question, k=5)
        
        # 2. Format context for the LLM
        context_parts = []
        for doc in docs:
            chunk_id = doc.metadata.get("chunk_id")
            context_parts.append(f"[ID: {chunk_id}]\n{doc.page_content}")
        
        context = "\n\n".join(context_parts)
        
        # 3. Get answer from LLM
        response = await self.chain.arun(context=context, question=question)
        
        # 4. Extract citations from metadata of retrieved docs
        citations = []
        for doc in docs:
            citations.append(Citation(
                chunk_id=doc.metadata.get("chunk_id"),
                document_id=doc.metadata.get("document_id"),
                source_file=doc.metadata.get("source", "unknown"),
                page=doc.metadata.get("page"),
                char_start=doc.metadata.get("char_start"),
                char_end=doc.metadata.get("char_end")
            ))
            
        return QueryResponse(
            answer=response,
            citations=citations
        )
