"""Prompt templates for RAG pipeline."""

from langchain_core.prompts import (
    ChatPromptTemplate,
    PromptTemplate,
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate
)


# System prompt for RAG
RAG_SYSTEM_PROMPT = """You are an expert AI assistant specialized in document analysis and question answering.

Your primary responsibilities:
1. Answer questions based STRICTLY on the provided context documents
2. Provide accurate, well-structured responses
3. Cite sources using the exact format [ID] where ID is the chunk_id
4. Acknowledge when information is insufficient or unavailable

Key guidelines:
- NEVER use information outside the provided context
- EVERY factual claim MUST include a citation
- Be concise but comprehensive
- Maintain a professional, helpful tone
- Structure longer responses with clear sections"""


RAG_HUMAN_TEMPLATE = """Based on the following context documents, please answer my question.

### Context Documents:
{context}

### Question:
{question}

### Instructions:
1. Answer using ONLY the information in the context documents
2. Include citations in [ID] format after each relevant statement
3. If the context doesn't contain enough information, clearly state that
4. Do not make assumptions or use external knowledge

### Answer:"""


# Main RAG prompt using ChatPromptTemplate (recommended for chat models)
RAG_CHAT_PROMPT = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(RAG_SYSTEM_PROMPT),
    HumanMessagePromptTemplate.from_template(RAG_HUMAN_TEMPLATE)
])


# Legacy PromptTemplate for backward compatibility
RAG_PROMPT_TEMPLATE = f"""{RAG_SYSTEM_PROMPT}

Context Documents:
{{context}}

Question: {{question}}

Answer with citations:"""

RAG_PROMPT = PromptTemplate(
    template=RAG_PROMPT_TEMPLATE,
    input_variables=["context", "question"]
)


# Specialized prompts for different use cases

SUMMARIZATION_PROMPT = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(
        """You are an expert document summarizer. 
        Create concise, accurate summaries that capture the key points.
        Always cite sources using [ID] format."""
    ),
    HumanMessagePromptTemplate.from_template(
        """Summarize the following documents:

{context}

Provide a comprehensive summary with citations:"""
    )
])


COMPARISON_PROMPT = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(
        """You are an expert analyst specializing in comparative analysis.
        Compare and contrast information from multiple documents.
        Cite all claims using [ID] format."""
    ),
    HumanMessagePromptTemplate.from_template(
        """Based on the following documents:

{context}

Compare and contrast regarding: {question}

Analysis with citations:"""
    )
])


EXTRACTION_PROMPT = ChatPromptTemplate.from_messages([
    SystemMessagePromptTemplate.from_template(
        """You are a data extraction specialist.
        Extract specific information as requested.
        Format output clearly and cite sources with [ID]."""
    ),
    HumanMessagePromptTemplate.from_template(
        """From the following documents:

{context}

Extract: {question}

Extracted information with citations:"""
    )
])


# Prompt registry for easy access
PROMPT_REGISTRY = {
    "rag": RAG_CHAT_PROMPT,
    "summarize": SUMMARIZATION_PROMPT,
    "compare": COMPARISON_PROMPT,
    "extract": EXTRACTION_PROMPT,
}


def get_prompt(prompt_type: str = "rag") -> ChatPromptTemplate:
    """Get a prompt template by type."""
    return PROMPT_REGISTRY.get(prompt_type, RAG_CHAT_PROMPT)