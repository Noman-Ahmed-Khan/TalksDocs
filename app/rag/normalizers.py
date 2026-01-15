"""Text normalization utilities for document processing."""

import re
import unicodedata
from typing import Optional
from functools import lru_cache


class TextNormalizer:
    """Handles text normalization and cleaning operations."""
    
    # Regex patterns compiled once
    WHITESPACE_PATTERN = re.compile(r'\s+')
    CONTROL_CHARS_PATTERN = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]')
    URL_PATTERN = re.compile(
        r'https?://(?:[-\w.]|(?:%[\da-fA-F]{2}))+[^\s]*',
        re.IGNORECASE
    )
    EMAIL_PATTERN = re.compile(r'[\w.+-]+@[\w-]+\.[\w.-]+')
    REPEATED_PUNCTUATION = re.compile(r'([.!?,;:]){2,}')
    MULTIPLE_NEWLINES = re.compile(r'\n{3,}')

    @classmethod
    def normalize(
        cls,
        text: str,
        lowercase: bool = False,
        remove_urls: bool = False,
        remove_emails: bool = False,
        normalize_unicode: bool = True,
        remove_control_chars: bool = True,
        normalize_whitespace: bool = True,
        max_length: Optional[int] = None
    ) -> str:
        """
        Apply comprehensive text normalization.
        
        Args:
            text: Input text to normalize
            lowercase: Convert to lowercase
            remove_urls: Remove URL patterns
            remove_emails: Remove email patterns
            normalize_unicode: Apply Unicode normalization
            remove_control_chars: Remove control characters
            normalize_whitespace: Collapse multiple whitespace
            max_length: Truncate to max length if specified
            
        Returns:
            Normalized text string
        """
        if not text:
            return ""
        
        result = text
        
        # Unicode normalization (NFKC for compatibility)
        if normalize_unicode:
            result = unicodedata.normalize('NFKC', result)
        
        # Remove control characters
        if remove_control_chars:
            result = cls.CONTROL_CHARS_PATTERN.sub('', result)
        
        # Remove URLs
        if remove_urls:
            result = cls.URL_PATTERN.sub('[URL]', result)
        
        # Remove emails
        if remove_emails:
            result = cls.EMAIL_PATTERN.sub('[EMAIL]', result)
        
        # Normalize repeated punctuation
        result = cls.REPEATED_PUNCTUATION.sub(r'\1', result)
        
        # Normalize multiple newlines
        result = cls.MULTIPLE_NEWLINES.sub('\n\n', result)
        
        # Normalize whitespace
        if normalize_whitespace:
            # Preserve paragraph breaks
            paragraphs = result.split('\n\n')
            paragraphs = [cls.WHITESPACE_PATTERN.sub(' ', p).strip() for p in paragraphs]
            result = '\n\n'.join(p for p in paragraphs if p)
        
        # Lowercase
        if lowercase:
            result = result.lower()
        
        # Truncate
        if max_length and len(result) > max_length:
            result = result[:max_length]
        
        return result.strip()

    @classmethod
    def clean_for_embedding(cls, text: str) -> str:
        """
        Clean text specifically for embedding generation.
        
        Optimizes text for semantic representation.
        """
        return cls.normalize(
            text,
            lowercase=False,
            remove_urls=True,
            remove_emails=True,
            normalize_unicode=True,
            remove_control_chars=True,
            normalize_whitespace=True
        )

    @classmethod
    def clean_for_display(cls, text: str, max_length: int = 500) -> str:
        """Clean and truncate text for display purposes."""
        cleaned = cls.normalize(text, normalize_whitespace=True)
        if len(cleaned) > max_length:
            return cleaned[:max_length - 3] + "..."
        return cleaned


class MetadataNormalizer:
    """Normalizes document metadata for consistency."""
    
    @staticmethod
    def normalize_source_path(path: str) -> str:
        """Extract clean filename from path."""
        import os
        return os.path.basename(path)
    
    @staticmethod
    def normalize_page_number(page: Optional[int]) -> Optional[int]:
        """Ensure page numbers are 1-indexed."""
        if page is None:
            return None
        return max(1, page + 1) if page == 0 else page
    
    @classmethod
    def normalize_metadata(cls, metadata: dict) -> dict:
        """Normalize all metadata fields."""
        normalized = metadata.copy()
        
        if 'source' in normalized:
            normalized['source_file'] = cls.normalize_source_path(normalized['source'])
        
        if 'page' in normalized:
            normalized['page'] = cls.normalize_page_number(normalized.get('page'))
        
        # Ensure required fields exist
        normalized.setdefault('source_file', 'unknown')
        normalized.setdefault('page', None)
        
        return normalized