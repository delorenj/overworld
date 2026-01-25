"""Hierarchy extraction service for document processing.

This module provides the main orchestration service for extracting
hierarchical structure from documents. It:
- Detects document type and routes to appropriate parser
- Provides AI-powered fallback for unstructured documents
- Integrates with R2 storage for content retrieval
- Stores extraction results in the database
"""

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.document import Document, DocumentStatus
from app.schemas.hierarchy import (
    ExtractionMethod,
    ExtractionResult,
    HierarchyExtractionResponse,
    HierarchyLevel,
    HierarchyNode,
    HierarchyTree,
    NodeType,
)
from app.services.markdown_parser import MarkdownParser
from app.services.pdf_parser import PDFParser
from app.services.r2_storage import R2StorageService, get_r2_service

logger = logging.getLogger(__name__)


class HierarchyExtractionError(Exception):
    """Raised when hierarchy extraction fails."""

    pass


class HierarchyExtractionService:
    """Service for extracting hierarchical structure from documents.

    This service coordinates the extraction pipeline:
    1. Retrieves document content from R2 storage
    2. Detects file type and routes to appropriate parser
    3. Falls back to AI inference for unstructured documents
    4. Stores results in the database
    """

    # MIME type to parser mapping
    PARSER_MAP = {
        "text/markdown": "markdown",
        "text/plain": "markdown",
        "text/x-markdown": "markdown",
        "application/pdf": "pdf",
    }

    def __init__(
        self,
        r2_service: Optional[R2StorageService] = None,
    ) -> None:
        """Initialize the extraction service.

        Args:
            r2_service: Optional R2 storage service (will create if not provided)
        """
        self._r2_service = r2_service or get_r2_service()
        self._ai_client: Optional[Any] = None
        self._initialize_ai_client()

    def _initialize_ai_client(self) -> None:
        """Initialize OpenRouter client for AI fallback."""
        if settings.OPENROUTER_API_KEY:
            try:
                from openrouter import OpenRouter as AsyncOpenRouter

                self._ai_client = AsyncOpenRouter(
                    api_key=settings.OPENROUTER_API_KEY,
                )
                logger.info("AI fallback client initialized")
            except ImportError:
                logger.warning("OpenRouter package not installed, AI fallback disabled")
        else:
            logger.warning("No OpenRouter API key configured, AI fallback disabled")

    async def extract_hierarchy(
        self,
        document: Document,
        db: AsyncSession,
        force_reprocess: bool = False,
        use_ai_fallback: bool = True,
    ) -> HierarchyExtractionResponse:
        """Extract hierarchy from a document.

        Args:
            document: Document model instance
            db: Database session for persistence
            force_reprocess: Force re-extraction even if already processed
            use_ai_fallback: Use AI inference if structured extraction fails

        Returns:
            HierarchyExtractionResponse with extraction results
        """
        import time

        start_time = time.time()

        # Check if already processed
        if (
            document.status == DocumentStatus.PROCESSED
            and document.processed_content
            and not force_reprocess
        ):
            logger.info(f"Document {document.id} already processed, returning cached result")
            return HierarchyExtractionResponse(
                document_id=document.id,
                status="already_processed",
                hierarchy=document.processed_content,
                statistics=self._get_cached_statistics(document.processed_content),
                processing_time_ms=int((time.time() - start_time) * 1000),
                error=None,
            )

        try:
            # Update status to processing
            document.status = DocumentStatus.PROCESSING
            await db.commit()

            # Get document content from R2
            content = await self._download_document_content(document)

            # Extract hierarchy based on file type
            result = await self._extract_by_type(
                content=content,
                mime_type=document.mime_type,
                filename=document.filename,
                use_ai_fallback=use_ai_fallback,
            )

            if not result.success or result.hierarchy is None:
                raise HierarchyExtractionError(result.error or "Unknown extraction error")

            # Convert to agent format for storage
            hierarchy_data = result.hierarchy.to_agent_format()

            # Calculate content hash
            content_hash = self._calculate_content_hash(hierarchy_data)

            # Update document with results
            document.processed_content = hierarchy_data
            document.content_hash = content_hash
            document.status = DocumentStatus.PROCESSED
            document.processed_at = datetime.now(timezone.utc)
            document.processing_error = None
            await db.commit()

            processing_time_ms = int((time.time() - start_time) * 1000)

            logger.info(
                f"Document {document.id} processed successfully in {processing_time_ms}ms"
            )

            return HierarchyExtractionResponse(
                document_id=document.id,
                status="processed",
                hierarchy=hierarchy_data,
                statistics=result.hierarchy.get_statistics(),
                processing_time_ms=processing_time_ms,
                error=None,
            )

        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            error_msg = str(e)

            logger.error(f"Document {document.id} extraction failed: {error_msg}")

            # Update document with error
            document.status = DocumentStatus.FAILED
            document.processing_error = error_msg
            await db.commit()

            return HierarchyExtractionResponse(
                document_id=document.id,
                status="failed",
                hierarchy=None,
                statistics=None,
                processing_time_ms=processing_time_ms,
                error=error_msg,
            )

    async def extract_from_content(
        self,
        content: bytes,
        filename: str,
        mime_type: str,
        use_ai_fallback: bool = True,
    ) -> ExtractionResult:
        """Extract hierarchy from raw content (no database interaction).

        Args:
            content: Raw document content bytes
            filename: Original filename
            mime_type: MIME type of the content
            use_ai_fallback: Use AI inference if structured extraction fails

        Returns:
            ExtractionResult with hierarchy
        """
        return await self._extract_by_type(
            content=content,
            mime_type=mime_type,
            filename=filename,
            use_ai_fallback=use_ai_fallback,
        )

    async def _download_document_content(self, document: Document) -> bytes:
        """Download document content from R2 storage.

        Args:
            document: Document model with R2 path

        Returns:
            Document content as bytes

        Raises:
            HierarchyExtractionError: If download fails
        """
        try:
            content = await self._r2_service.download_file(
                bucket_name=settings.R2_BUCKET_UPLOADS,
                r2_path=document.r2_path,
            )
            return content
        except Exception as e:
            raise HierarchyExtractionError(f"Failed to download document: {str(e)}")

    async def _extract_by_type(
        self,
        content: bytes,
        mime_type: str,
        filename: str,
        use_ai_fallback: bool = True,
    ) -> ExtractionResult:
        """Extract hierarchy based on detected file type.

        Args:
            content: Raw document content
            mime_type: MIME type of the content
            filename: Original filename
            use_ai_fallback: Use AI inference if structured extraction fails

        Returns:
            ExtractionResult with hierarchy
        """
        parser_type = self.PARSER_MAP.get(mime_type, "unknown")

        if parser_type == "markdown":
            # Decode content for markdown parsing
            try:
                text_content = content.decode("utf-8")
            except UnicodeDecodeError:
                text_content = content.decode("utf-8", errors="replace")

            result = MarkdownParser.extract_with_result(
                markdown_content=text_content,
                filename=filename,
                source_mime_type=mime_type,
            )

        elif parser_type == "pdf":
            result = PDFParser.extract_with_result(
                pdf_content=content,
                filename=filename,
                source_mime_type=mime_type,
            )

        else:
            # Unknown type - try markdown first, then AI fallback
            try:
                text_content = content.decode("utf-8")
                result = MarkdownParser.extract_with_result(
                    markdown_content=text_content,
                    filename=filename,
                    source_mime_type=mime_type,
                )
            except (UnicodeDecodeError, Exception):
                result = ExtractionResult.failure(
                    error=f"Unsupported file type: {mime_type}",
                    processing_time_ms=0,
                )

        # Check if we need AI fallback
        if (
            use_ai_fallback
            and result.success
            and result.hierarchy
            and result.hierarchy.confidence_score < 0.5
        ):
            logger.info(
                f"Low confidence ({result.hierarchy.confidence_score:.2f}) for {filename}, "
                "attempting AI inference"
            )
            ai_result = await self._ai_fallback_extraction(content, filename, mime_type)
            if ai_result.success and ai_result.hierarchy:
                if ai_result.hierarchy.confidence_score > result.hierarchy.confidence_score:
                    return ai_result

        # AI fallback for failed extractions
        if not result.success and use_ai_fallback:
            logger.info(f"Extraction failed for {filename}, attempting AI fallback")
            return await self._ai_fallback_extraction(content, filename, mime_type)

        return result

    async def _ai_fallback_extraction(
        self,
        content: bytes,
        filename: str,
        mime_type: str,
    ) -> ExtractionResult:
        """Use AI to infer document structure.

        Args:
            content: Raw document content
            filename: Original filename
            mime_type: MIME type

        Returns:
            ExtractionResult with AI-inferred hierarchy
        """
        import time

        start_time = time.time()

        if not self._ai_client:
            return ExtractionResult.failure(
                error="AI fallback not available (no API key configured)",
                processing_time_ms=int((time.time() - start_time) * 1000),
            )

        try:
            # Decode content for AI analysis
            try:
                text_content = content.decode("utf-8")
            except UnicodeDecodeError:
                text_content = content.decode("utf-8", errors="replace")

            # Truncate for API limits
            max_chars = 15000
            if len(text_content) > max_chars:
                text_content = text_content[:max_chars] + "\n...[truncated]..."

            # Build prompt
            prompt = self._build_ai_extraction_prompt(text_content, filename)

            # Call LLM
            completion = await self._ai_client.chat.completions.create(
                model="openai/gpt-4-turbo-preview",
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a document structure analyst. Extract hierarchical "
                            "structure from documents into L0-L4 levels. L0 is the document "
                            "root, L1 are main sections, L2 subsections, L3 details, L4 "
                            "fine-grained elements. Respond with valid JSON only."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=4000,
            )

            # Parse response
            response_text = completion.choices[0].message.content
            hierarchy = self._parse_ai_response(response_text, filename, mime_type)

            processing_time_ms = int((time.time() - start_time) * 1000)

            return ExtractionResult(
                success=True,
                hierarchy=hierarchy,
                error=None,
                processing_time_ms=processing_time_ms,
            )

        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"AI extraction failed: {e}")

            return ExtractionResult.failure(
                error=f"AI extraction failed: {str(e)}",
                processing_time_ms=processing_time_ms,
            )

    def _build_ai_extraction_prompt(self, content: str, filename: str) -> str:
        """Build prompt for AI hierarchy extraction.

        Args:
            content: Document text content
            filename: Original filename

        Returns:
            Prompt string for LLM
        """
        return f"""Analyze this document and extract its hierarchical structure.

Document: {filename}

Content:
---
{content}
---

Extract the structure into exactly this JSON format:
{{
    "title": "Document title",
    "L1": [
        {{"id": "l1_1", "title": "Main section 1"}},
        {{"id": "l1_2", "title": "Main section 2"}}
    ],
    "L2": [
        {{"id": "l2_1", "title": "Subsection 1.1", "parent_id": "l1_1"}},
        {{"id": "l2_2", "title": "Subsection 1.2", "parent_id": "l1_1"}}
    ],
    "L3": [
        {{"id": "l3_1", "title": "Detail 1.1.1", "parent_id": "l2_1"}}
    ],
    "L4": []
}}

Rules:
1. Identify main sections (L1) - these are the top-level topics or chapters
2. Identify subsections (L2) that belong under L1 sections
3. Identify details (L3) that belong under L2 sections
4. Identify fine-grained elements (L4) if present
5. Each item needs a unique id and title
6. L2-L4 items should have parent_id referencing their parent
7. If document has no clear structure, create logical groupings
8. Return ONLY valid JSON, no explanation text"""

    def _parse_ai_response(
        self,
        response: str,
        filename: str,
        mime_type: str,
    ) -> HierarchyTree:
        """Parse AI response into HierarchyTree.

        Args:
            response: Raw AI response text
            filename: Original filename
            mime_type: MIME type

        Returns:
            HierarchyTree from AI response
        """
        # Extract JSON from response
        json_str = response.strip()

        # Handle markdown code blocks
        if "```json" in json_str:
            json_str = json_str.split("```json")[1].split("```")[0]
        elif "```" in json_str:
            json_str = json_str.split("```")[1].split("```")[0]

        try:
            data = json.loads(json_str)
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse AI JSON response: {e}")
            # Return minimal hierarchy
            return self._create_minimal_hierarchy(filename, mime_type)

        # Build HierarchyTree from parsed data
        return self._build_hierarchy_from_ai_data(data, filename, mime_type)

    def _build_hierarchy_from_ai_data(
        self,
        data: Dict[str, Any],
        filename: str,
        mime_type: str,
    ) -> HierarchyTree:
        """Build HierarchyTree from AI-extracted data.

        Args:
            data: Parsed AI response data
            filename: Original filename
            mime_type: MIME type

        Returns:
            HierarchyTree
        """
        doc_title = data.get("title", filename)

        # Create root node
        root_node = HierarchyNode(
            id="root",
            title=doc_title,
            type=NodeType.ROOT,
            level=0,
            content=f"AI-extracted: {filename}",
        )

        # Process levels
        def parse_items(items: list, level: int) -> list:
            nodes = []
            for item in items:
                if isinstance(item, dict):
                    node = HierarchyNode(
                        id=item.get("id", f"ai_{level}_{len(nodes)}"),
                        title=item.get("title", "Untitled"),
                        type=NodeType.AI_INFERRED,
                        level=level,
                        content=item.get("title"),
                        parent_id=item.get("parent_id"),
                    )
                    nodes.append(node)
            return nodes

        l1_items = parse_items(data.get("L1", []), 1)
        l2_items = parse_items(data.get("L2", []), 2)
        l3_items = parse_items(data.get("L3", []), 3)
        l4_items = parse_items(data.get("L4", []), 4)

        # Ensure at least one L1 item
        if not l1_items:
            l1_items.append(
                HierarchyNode(
                    id="empty_l1",
                    title="Document Content",
                    type=NodeType.EMPTY,
                    level=1,
                    parent_id="root",
                )
            )

        # Calculate statistics
        total_nodes = 1 + len(l1_items) + len(l2_items) + len(l3_items) + len(l4_items)
        max_depth = 1
        if l4_items:
            max_depth = 4
        elif l3_items:
            max_depth = 3
        elif l2_items:
            max_depth = 2

        return HierarchyTree(
            L0=HierarchyLevel(
                title=doc_title,
                description="Document root (AI-inferred)",
                items=[root_node],
            ),
            L1=HierarchyLevel(
                title="Main Sections",
                description="AI-inferred main sections",
                items=l1_items,
            ),
            L2=HierarchyLevel(
                title="Subsections",
                description="AI-inferred subsections",
                items=l2_items,
            ),
            L3=HierarchyLevel(
                title="Details",
                description="AI-inferred details",
                items=l3_items,
            ),
            L4=HierarchyLevel(
                title="Fine-grained Elements",
                description="AI-inferred elements",
                items=l4_items,
            ),
            extraction_method=ExtractionMethod.AI_INFERENCE,
            source_filename=filename,
            source_mime_type=mime_type,
            total_nodes=total_nodes,
            max_depth=max_depth,
            extracted_at=datetime.utcnow(),
            confidence_score=0.7,  # Moderate confidence for AI inference
            warnings=["Structure inferred by AI, may need review"],
        )

    def _create_minimal_hierarchy(
        self,
        filename: str,
        mime_type: str,
    ) -> HierarchyTree:
        """Create minimal hierarchy for failed extractions.

        Args:
            filename: Original filename
            mime_type: MIME type

        Returns:
            Minimal HierarchyTree
        """
        root_node = HierarchyNode(
            id="root",
            title=filename,
            type=NodeType.ROOT,
            level=0,
        )

        empty_l1 = HierarchyNode(
            id="empty_l1",
            title="Document Content",
            type=NodeType.EMPTY,
            level=1,
            parent_id="root",
        )

        return HierarchyTree(
            L0=HierarchyLevel(
                title=filename,
                description="Document root",
                items=[root_node],
            ),
            L1=HierarchyLevel(
                title="Content",
                description="Unable to extract structure",
                items=[empty_l1],
            ),
            L2=HierarchyLevel(title="Subsections", items=[]),
            L3=HierarchyLevel(title="Details", items=[]),
            L4=HierarchyLevel(title="Elements", items=[]),
            extraction_method=ExtractionMethod.FALLBACK,
            source_filename=filename,
            source_mime_type=mime_type,
            total_nodes=2,
            max_depth=1,
            extracted_at=datetime.utcnow(),
            confidence_score=0.1,
            warnings=["Could not extract document structure"],
        )

    def _calculate_content_hash(self, content: Dict[str, Any]) -> str:
        """Calculate SHA-256 hash of content for deduplication.

        Args:
            content: Content dictionary to hash

        Returns:
            SHA-256 hash string
        """
        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()

    def _get_cached_statistics(
        self, processed_content: Optional[Dict[str, Any]]
    ) -> Optional[Dict[str, Any]]:
        """Get statistics from cached processed content.

        Args:
            processed_content: Previously extracted content

        Returns:
            Statistics dictionary or None
        """
        if not processed_content:
            return None

        try:
            level_counts = {
                "L0": 1 if processed_content.get("L0") else 0,
                "L1": len(processed_content.get("L1", [])),
                "L2": len(processed_content.get("L2", [])),
                "L3": len(processed_content.get("L3", [])),
                "L4": len(processed_content.get("L4", [])),
            }

            total_nodes = sum(level_counts.values())

            # Calculate max depth
            max_depth = 0
            for level, count in level_counts.items():
                if count > 0:
                    max_depth = int(level[1])

            return {
                "total_nodes": total_nodes,
                "max_depth": max_depth,
                "nodes_by_level": level_counts,
                "extraction_method": "cached",
                "confidence_score": 1.0,
            }
        except Exception:
            return None


# Module-level service instance (lazy initialization)
_extraction_service: Optional[HierarchyExtractionService] = None


def get_hierarchy_extraction_service() -> HierarchyExtractionService:
    """Get or create the hierarchy extraction service instance.

    Returns:
        HierarchyExtractionService instance
    """
    global _extraction_service
    if _extraction_service is None:
        _extraction_service = HierarchyExtractionService()
    return _extraction_service
