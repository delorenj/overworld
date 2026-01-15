"""Enhanced document processor supporting both markdown and PDF parsing."""

import logging
from typing import Dict, Optional, Union

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.queue import get_rabbitmq
from app.models.document import Document, DocumentStatus
from app.models.generation_job import GenerationJob, JobStatus
from app.schemas.document import HierarchyNode
from app.services.markdown_parser import MarkdownParser
from app.services.pdf_parser import PDFParser
from app.utils import FileValidationError, get_mime_type, validate_file_size, validate_file_type
import logging

logger = logging.getLogger(__name__)


class DocumentProcessor:
    """Enhanced document processor supporting both markdown and PDF parsing."""

    @staticmethod
    def process_document(db: AsyncSession, document_id: str) -> Optional[GenerationJob]:
        """
        Process uploaded document and trigger generation job.

        Args:
            db: Database session
            document_id: Document UUID to process

        Returns:
            Created generation job or None if processing failed
        """
        # Get document
        document = await db.get(Document, document_id)
        if not document:
            logger.error(f"Document {document_id} not found")
            return None

        if document.status != DocumentStatus.UPLOADED:
            logger.warning(f"Document {document_id} already processed (status: {document.status})")
            return None

        try:
            # Update document status to processing
            document.status = DocumentStatus.PROCESSING
            await db.commit()

            # Extract hierarchy based on document type
            if document.mime_type.startswith("text/markdown"):
                hierarchy = await MarkdownParser.extract_hierarchy(document)
            elif document.mime_type == "application/pdf":
                hierarchy = await PDFParser.extract_hierarchy(document)
            else:
                raise ValueError(f"Unsupported document type: {document.mime_type}")

            # Update document with processed content
            document.processed_content = hierarchy
            document.content_hash = DocumentProcessor._calculate_content_hash(hierarchy)
            document.status = DocumentStatus.PROCESSED
            await db.commit()

            # Create generation job
            job = GenerationJob(
                document_id=document_id,
                user_id=document.user_id,
                status=JobStatus.PENDING,
                agent_state={"parser": {"complete": True}, "current_stage": "parser"},
            )
            db.add(job)
            await db.commit()

            # Publish job to queue
            rabbitmq = await get_rabbitmq()
            message_body = json.dumps(
                {"job_id": job.id, "document_id": str(document_id), "user_id": document.user_id}
            ).encode()

            await rabbitmq.publish_message("generation.pending", message_body)

            logger.info(f"Document {document_id} processed and job {job.id} created")
            return job

        except Exception as e:
            logger.error(f"Failed to process document {document_id}: {str(e)}")
            document.status = DocumentStatus.FAILED
            document.processing_error = str(e)
            await db.commit()
            return None

    @staticmethod
    async def _extract_hierarchy(document: Document) -> Dict:
        """
        Extract hierarchy structure from document content.

        Args:
            document: Document to extract hierarchy from

        Returns:
            Dictionary representing L0-L4 hierarchy
        """
        # Read document content from R2 storage
        try:
            content = await DocumentProcessor._read_document_content(document)
        except Exception as e:
            logger.error(f"Failed to read document content from R2: {str(e)}")
            # Return basic hierarchy on error
            return {
                "level_0": {"title": document.filename, "description": "Document root"},
                "level_1": {
                    "title": "Error",
                    "items": [{"type": "error", "content": f"Failed to read document: {str(e)}"}],
                },
                "level_2": {"title": "Error", "items": []},
                "level_3": {"title": "Error", "items": []},
                "level_4": {"title": "Error", "items": []},
            }

        # Extract hierarchy based on document type
        if document.mime_type.startswith("text/markdown"):
            return await MarkdownParser.extract_hierarchy(document)
        elif document.mime_type == "application/pdf":
            return await PDFParser.extract_hierarchy(document)
        else:
            raise ValueError(f"Unsupported document type: {document.mime_type}")

    @staticmethod
    async def _read_document_content(document: Document) -> str:
        """
        Read document content from R2 storage.

        Args:
            document: Document with R2 storage information

        Returns:
            Document content as string
        """
        # TODO: Implement actual R2 download in STORY-002
        # For now, return placeholder content for PDFs
        if document.mime_type == "application/pdf":
            return f"PDF content for {document.filename} (not yet implemented)"
        else:
            # For markdown files, return the placeholder content
            # TODO: Read actual markdown content from R2 storage
            return f"Markdown content for {document.filename} (not yet implemented)"

    @staticmethod
    def _calculate_content_hash(content: Dict) -> str:
        """
        Calculate SHA-256 hash of content for deduplication.

        Args:
            content: Content dictionary to hash

        Returns:
            SHA-256 hash string
        """
        import json

        content_str = json.dumps(content, sort_keys=True)
        return hashlib.sha256(content_str.encode()).hexdigest()
