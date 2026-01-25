"""PDF parser service for hierarchical structure extraction.

This module provides PDF parsing capabilities using pypdf to extract
a hierarchical L0-L4 structure from PDF documents. It handles:
- PDF Table of Contents (outline/bookmarks)
- Text-based structure inference
- Header detection via font size analysis
- Page-level organization
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from io import BytesIO
from typing import Any, Dict, List, Optional, Tuple

from pypdf import PdfReader
from pypdf.generic import Destination

from app.schemas.hierarchy import (
    ExtractionMethod,
    ExtractionResult,
    HierarchyLevel,
    HierarchyNode,
    HierarchyTree,
    NodeType,
)

logger = logging.getLogger(__name__)


@dataclass
class TOCEntry:
    """Represents a Table of Contents entry from PDF outline."""

    title: str
    level: int
    page_number: Optional[int]
    children: List["TOCEntry"] = field(default_factory=list)


@dataclass
class TextBlock:
    """Represents a block of text extracted from PDF."""

    text: str
    page_number: int
    is_header: bool = False
    font_size: Optional[float] = None
    line_number: int = 0


class PDFParser:
    """Parser for PDF documents that extracts hierarchical structure.

    Attempts extraction in this order:
    1. PDF outline/bookmarks (TOC) - most reliable
    2. Text-based structure inference using font sizes and formatting
    3. Page-based organization as fallback
    """

    # Maximum depth for TOC traversal
    MAX_TOC_DEPTH = 10

    # Header detection patterns
    HEADER_PATTERNS = [
        r"^(\d+\.)+\s+",  # Numbered headers: 1.1 or 1.2.3
        r"^Chapter\s+\d+",  # Chapter X
        r"^Section\s+\d+",  # Section X
        r"^Part\s+[IVX\d]+",  # Part I, Part 1
        r"^Appendix\s+[A-Z]",  # Appendix A
    ]

    def __init__(self) -> None:
        """Initialize the PDF parser."""
        self._compiled_patterns = [re.compile(p, re.IGNORECASE) for p in self.HEADER_PATTERNS]

    @classmethod
    def extract_hierarchy(
        cls,
        pdf_content: bytes,
        filename: str,
        source_mime_type: str = "application/pdf",
    ) -> HierarchyTree:
        """Extract hierarchical L0-L4 structure from PDF content.

        Args:
            pdf_content: Raw PDF bytes
            filename: Original filename for context
            source_mime_type: MIME type of source document

        Returns:
            HierarchyTree with extracted structure
        """
        parser = cls()
        return parser._extract(pdf_content, filename, source_mime_type)

    @classmethod
    def extract_with_result(
        cls,
        pdf_content: bytes,
        filename: str,
        source_mime_type: str = "application/pdf",
    ) -> ExtractionResult:
        """Extract hierarchy with full result wrapper including timing.

        Args:
            pdf_content: Raw PDF bytes
            filename: Original filename for context
            source_mime_type: MIME type of source

        Returns:
            ExtractionResult with hierarchy and metadata
        """
        import time

        start_time = time.time()

        try:
            hierarchy = cls.extract_hierarchy(pdf_content, filename, source_mime_type)
            processing_time_ms = int((time.time() - start_time) * 1000)

            return ExtractionResult(
                success=True,
                hierarchy=hierarchy,
                error=None,
                processing_time_ms=processing_time_ms,
            )
        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"PDF extraction failed for {filename}: {str(e)}")

            return ExtractionResult.failure(
                error=f"PDF extraction failed: {str(e)}",
                processing_time_ms=processing_time_ms,
            )

    def _extract(
        self,
        pdf_content: bytes,
        filename: str,
        source_mime_type: str,
    ) -> HierarchyTree:
        """Internal extraction method.

        Args:
            pdf_content: Raw PDF bytes
            filename: Source filename
            source_mime_type: MIME type

        Returns:
            HierarchyTree with extracted hierarchy
        """
        try:
            pdf_file = BytesIO(pdf_content)
            reader = PdfReader(pdf_file)
        except Exception as e:
            logger.error(f"Failed to read PDF: {e}")
            raise ValueError(f"Invalid PDF file: {str(e)}")

        # Get PDF metadata
        metadata = self._extract_metadata(reader, filename)
        page_count = len(reader.pages)

        # Try to extract TOC from outline
        toc_entries = self._extract_toc(reader)

        if toc_entries:
            # Build hierarchy from TOC
            return self._build_hierarchy_from_toc(
                toc_entries=toc_entries,
                filename=filename,
                source_mime_type=source_mime_type,
                metadata=metadata,
                page_count=page_count,
            )

        # Fallback: Extract text and infer structure
        logger.info(f"No TOC found in {filename}, falling back to text structure inference")

        text_blocks = self._extract_text_blocks(reader)
        if text_blocks:
            return self._build_hierarchy_from_text(
                text_blocks=text_blocks,
                filename=filename,
                source_mime_type=source_mime_type,
                metadata=metadata,
                page_count=page_count,
            )

        # Final fallback: Page-based hierarchy
        logger.info(f"No structure found in {filename}, using page-based fallback")
        return self._build_fallback_hierarchy(
            filename=filename,
            source_mime_type=source_mime_type,
            metadata=metadata,
            page_count=page_count,
        )

    def _extract_metadata(self, reader: PdfReader, filename: str) -> Dict[str, Any]:
        """Extract PDF metadata.

        Args:
            reader: PyPDF reader instance
            filename: Fallback filename

        Returns:
            Dictionary with metadata
        """
        metadata: Dict[str, Any] = {
            "page_count": len(reader.pages),
            "filename": filename,
        }

        try:
            if reader.metadata:
                if reader.metadata.title:
                    metadata["title"] = str(reader.metadata.title)
                if reader.metadata.author:
                    metadata["author"] = str(reader.metadata.author)
                if reader.metadata.subject:
                    metadata["subject"] = str(reader.metadata.subject)
                if reader.metadata.creator:
                    metadata["creator"] = str(reader.metadata.creator)
        except Exception as e:
            logger.debug(f"Could not extract PDF metadata: {e}")

        return metadata

    def _extract_toc(self, reader: PdfReader) -> List[TOCEntry]:
        """Extract Table of Contents from PDF outline/bookmarks.

        Args:
            reader: PyPDF reader instance

        Returns:
            List of TOCEntry objects representing the outline
        """
        toc_entries: List[TOCEntry] = []

        try:
            outline = reader.outline
            if not outline:
                return []

            # Process outline recursively
            self._process_outline_items(reader, outline, toc_entries, level=0)

        except Exception as e:
            logger.debug(f"Could not extract PDF outline: {e}")
            return []

        return toc_entries

    def _process_outline_items(
        self,
        reader: PdfReader,
        items: List[Any],
        toc_entries: List[TOCEntry],
        level: int,
    ) -> None:
        """Recursively process PDF outline items.

        Args:
            reader: PyPDF reader instance
            items: List of outline items
            toc_entries: List to append entries to
            level: Current nesting level
        """
        if level > self.MAX_TOC_DEPTH:
            return

        for item in items:
            if isinstance(item, list):
                # Nested list means children of the previous item
                if toc_entries:
                    self._process_outline_items(
                        reader, item, toc_entries[-1].children, level + 1
                    )
            elif isinstance(item, Destination):
                # This is a bookmark destination
                title = str(item.title) if item.title else "Untitled"
                page_num = self._get_page_number(reader, item)

                entry = TOCEntry(
                    title=title.strip(),
                    level=level,
                    page_number=page_num,
                )
                toc_entries.append(entry)
            elif hasattr(item, "title"):
                # Handle dictionary-style bookmarks
                title = str(item.title) if item.title else "Untitled"
                page_num = self._get_page_number(reader, item)

                entry = TOCEntry(
                    title=title.strip(),
                    level=level,
                    page_number=page_num,
                )
                toc_entries.append(entry)

    def _get_page_number(self, reader: PdfReader, item: Any) -> Optional[int]:
        """Get page number from outline item.

        Args:
            reader: PyPDF reader instance
            item: Outline item

        Returns:
            1-indexed page number or None
        """
        try:
            if hasattr(item, "page"):
                page_obj = item.page
                if page_obj is not None:
                    # Find the page index
                    for i, page in enumerate(reader.pages):
                        if page.indirect_reference == page_obj:
                            return i + 1  # 1-indexed
                        if hasattr(page_obj, "idnum") and hasattr(
                            page.indirect_reference, "idnum"
                        ):
                            if page.indirect_reference.idnum == page_obj.idnum:
                                return i + 1
        except Exception as e:
            logger.debug(f"Could not determine page number: {e}")

        return None

    def _extract_text_blocks(self, reader: PdfReader) -> List[TextBlock]:
        """Extract text blocks from PDF pages for structure inference.

        Args:
            reader: PyPDF reader instance

        Returns:
            List of TextBlock objects
        """
        text_blocks: List[TextBlock] = []
        line_counter = 0

        for page_num, page in enumerate(reader.pages, 1):
            try:
                text = page.extract_text() or ""
                lines = text.split("\n")

                for line in lines:
                    line = line.strip()
                    if not line:
                        continue

                    line_counter += 1
                    is_header = self._is_likely_header(line)

                    text_blocks.append(
                        TextBlock(
                            text=line,
                            page_number=page_num,
                            is_header=is_header,
                            line_number=line_counter,
                        )
                    )

            except Exception as e:
                logger.debug(f"Could not extract text from page {page_num}: {e}")

        return text_blocks

    def _is_likely_header(self, text: str) -> bool:
        """Check if text is likely a header based on patterns.

        Args:
            text: Text to check

        Returns:
            True if text appears to be a header
        """
        # Check against header patterns
        for pattern in self._compiled_patterns:
            if pattern.match(text):
                return True

        # Check for all caps (common header style)
        if text.isupper() and len(text.split()) <= 6:
            return True

        # Check for title case with limited words
        words = text.split()
        if len(words) <= 8 and text.istitle():
            return True

        return False

    def _build_hierarchy_from_toc(
        self,
        toc_entries: List[TOCEntry],
        filename: str,
        source_mime_type: str,
        metadata: Dict[str, Any],
        page_count: int,
    ) -> HierarchyTree:
        """Build HierarchyTree from TOC entries.

        Args:
            toc_entries: Extracted TOC entries
            filename: Source filename
            source_mime_type: MIME type
            metadata: PDF metadata
            page_count: Total page count

        Returns:
            Complete HierarchyTree
        """
        # Flatten TOC to get all entries with their levels
        flat_entries = self._flatten_toc(toc_entries)

        # Initialize levels
        l0_items: List[HierarchyNode] = []
        l1_items: List[HierarchyNode] = []
        l2_items: List[HierarchyNode] = []
        l3_items: List[HierarchyNode] = []
        l4_items: List[HierarchyNode] = []

        # Create root node
        doc_title = metadata.get("title", self._clean_filename(filename))
        root_node = HierarchyNode(
            id="root",
            title=doc_title,
            type=NodeType.ROOT,
            level=0,
            content=f"PDF Document: {filename}",
            page_number=1,
            metadata={
                "page_count": page_count,
                "author": metadata.get("author"),
            },
        )
        l0_items.append(root_node)

        # Track parents and max depth
        current_parents: Dict[int, str] = {0: "root"}
        max_depth = 0
        warnings: List[str] = []
        node_counter = 0

        for entry, toc_level in flat_entries:
            node_counter += 1
            node_id = f"toc_{node_counter}"

            # Map TOC level to hierarchy level (0 -> L1, 1 -> L2, etc.)
            h_level = min(4, toc_level + 1)
            max_depth = max(max_depth, h_level)

            # Update parent tracking
            parent_id = current_parents.get(h_level - 1, "root")
            current_parents[h_level] = node_id

            # Clear child level parents
            for l in range(h_level + 1, 5):
                current_parents.pop(l, None)

            node = HierarchyNode(
                id=node_id,
                title=entry.title,
                type=NodeType.TOC_ENTRY,
                level=h_level,
                content=entry.title,
                page_number=entry.page_number,
                parent_id=parent_id,
                metadata={"toc_level": toc_level},
            )

            # Add to appropriate level
            if h_level == 1:
                l1_items.append(node)
            elif h_level == 2:
                l2_items.append(node)
            elif h_level == 3:
                l3_items.append(node)
            else:
                l4_items.append(node)

        # Ensure at least one L1 item
        if not l1_items:
            warnings.append("PDF TOC has no top-level entries")
            l1_items.append(
                HierarchyNode(
                    id="empty_l1",
                    title="Document Content",
                    type=NodeType.EMPTY,
                    level=1,
                    parent_id="root",
                )
            )

        total_nodes = len(l0_items) + len(l1_items) + len(l2_items) + len(l3_items) + len(l4_items)

        return HierarchyTree(
            L0=HierarchyLevel(
                title=doc_title,
                description="Document root",
                items=l0_items,
            ),
            L1=HierarchyLevel(
                title="Main Sections",
                description="Top-level TOC entries",
                items=l1_items,
            ),
            L2=HierarchyLevel(
                title="Subsections",
                description="Second-level TOC entries",
                items=l2_items,
            ),
            L3=HierarchyLevel(
                title="Details",
                description="Third-level TOC entries",
                items=l3_items,
            ),
            L4=HierarchyLevel(
                title="Fine-grained Elements",
                description="Deep TOC entries",
                items=l4_items,
            ),
            extraction_method=ExtractionMethod.PDF_TOC,
            source_filename=filename,
            source_mime_type=source_mime_type,
            total_nodes=total_nodes,
            max_depth=max_depth,
            extracted_at=datetime.utcnow(),
            confidence_score=0.95 if len(flat_entries) > 3 else 0.8,
            warnings=warnings,
        )

    def _flatten_toc(
        self, entries: List[TOCEntry], current_level: int = 0
    ) -> List[Tuple[TOCEntry, int]]:
        """Flatten nested TOC entries into a list with levels.

        Args:
            entries: Nested TOC entries
            current_level: Current nesting level

        Returns:
            List of (entry, level) tuples
        """
        result: List[Tuple[TOCEntry, int]] = []

        for entry in entries:
            result.append((entry, current_level))
            if entry.children:
                result.extend(self._flatten_toc(entry.children, current_level + 1))

        return result

    def _build_hierarchy_from_text(
        self,
        text_blocks: List[TextBlock],
        filename: str,
        source_mime_type: str,
        metadata: Dict[str, Any],
        page_count: int,
    ) -> HierarchyTree:
        """Build HierarchyTree from text block analysis.

        Args:
            text_blocks: Extracted text blocks
            filename: Source filename
            source_mime_type: MIME type
            metadata: PDF metadata
            page_count: Total page count

        Returns:
            Complete HierarchyTree
        """
        # Initialize levels
        l0_items: List[HierarchyNode] = []
        l1_items: List[HierarchyNode] = []
        l2_items: List[HierarchyNode] = []
        l3_items: List[HierarchyNode] = []
        l4_items: List[HierarchyNode] = []

        # Create root node
        doc_title = metadata.get("title", self._clean_filename(filename))
        root_node = HierarchyNode(
            id="root",
            title=doc_title,
            type=NodeType.ROOT,
            level=0,
            content=f"PDF Document: {filename}",
            page_number=1,
        )
        l0_items.append(root_node)

        # Find headers in text blocks
        headers = [block for block in text_blocks if block.is_header]
        warnings: List[str] = []
        max_depth = 0
        node_counter = 0
        current_parents: Dict[int, str] = {0: "root"}

        if not headers:
            warnings.append("No header patterns detected in PDF text")
            # Use first few non-empty lines as structure
            for block in text_blocks[:10]:
                if len(block.text) < 100:  # Likely not a paragraph
                    node_counter += 1
                    l1_items.append(
                        HierarchyNode(
                            id=f"text_{node_counter}",
                            title=block.text[:100],
                            type=NodeType.PARAGRAPH,
                            level=1,
                            content=block.text,
                            page_number=block.page_number,
                            line_number=block.line_number,
                            parent_id="root",
                        )
                    )
                    max_depth = 1
        else:
            # Build hierarchy from detected headers
            for block in headers:
                node_counter += 1
                node_id = f"header_{node_counter}"

                # Determine level based on header characteristics
                h_level = self._infer_header_level(block.text)
                max_depth = max(max_depth, h_level)

                parent_id = current_parents.get(h_level - 1, "root")
                current_parents[h_level] = node_id

                node = HierarchyNode(
                    id=node_id,
                    title=block.text[:100],
                    type=NodeType.HEADER,
                    level=h_level,
                    content=block.text,
                    page_number=block.page_number,
                    line_number=block.line_number,
                    parent_id=parent_id,
                )

                if h_level == 1:
                    l1_items.append(node)
                elif h_level == 2:
                    l2_items.append(node)
                elif h_level == 3:
                    l3_items.append(node)
                else:
                    l4_items.append(node)

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
            warnings.append("No L1 structure could be inferred from PDF text")

        total_nodes = len(l0_items) + len(l1_items) + len(l2_items) + len(l3_items) + len(l4_items)

        return HierarchyTree(
            L0=HierarchyLevel(
                title=doc_title,
                description="Document root",
                items=l0_items,
            ),
            L1=HierarchyLevel(
                title="Main Sections",
                description="Detected headers",
                items=l1_items,
            ),
            L2=HierarchyLevel(
                title="Subsections",
                description="Secondary headers",
                items=l2_items,
            ),
            L3=HierarchyLevel(
                title="Details",
                description="Detail headers",
                items=l3_items,
            ),
            L4=HierarchyLevel(
                title="Fine-grained Elements",
                description="Sub-detail headers",
                items=l4_items,
            ),
            extraction_method=ExtractionMethod.PDF_STRUCTURE,
            source_filename=filename,
            source_mime_type=source_mime_type,
            total_nodes=total_nodes,
            max_depth=max_depth,
            extracted_at=datetime.utcnow(),
            confidence_score=0.6,  # Lower confidence for text inference
            warnings=warnings,
        )

    def _infer_header_level(self, text: str) -> int:
        """Infer header level from text characteristics.

        Args:
            text: Header text

        Returns:
            Hierarchy level (1-4)
        """
        # Check for numbered headers
        number_match = re.match(r"^(\d+)\.(\d+)?\.?(\d+)?\.?\s", text)
        if number_match:
            groups = [g for g in number_match.groups() if g]
            return min(4, len(groups))

        # Check for "Chapter" (L1)
        if re.match(r"^Chapter\s+", text, re.IGNORECASE):
            return 1

        # Check for "Part" (L1)
        if re.match(r"^Part\s+", text, re.IGNORECASE):
            return 1

        # Check for "Section" (L2)
        if re.match(r"^Section\s+", text, re.IGNORECASE):
            return 2

        # Check for "Appendix" (L1)
        if re.match(r"^Appendix\s+", text, re.IGNORECASE):
            return 1

        # Check for all caps (typically L1)
        if text.isupper():
            return 1

        # Default to L2 for other detected headers
        return 2

    def _build_fallback_hierarchy(
        self,
        filename: str,
        source_mime_type: str,
        metadata: Dict[str, Any],
        page_count: int,
    ) -> HierarchyTree:
        """Build minimal fallback hierarchy based on pages.

        Args:
            filename: Source filename
            source_mime_type: MIME type
            metadata: PDF metadata
            page_count: Total page count

        Returns:
            Basic HierarchyTree
        """
        doc_title = metadata.get("title", self._clean_filename(filename))

        root_node = HierarchyNode(
            id="root",
            title=doc_title,
            type=NodeType.ROOT,
            level=0,
            content=f"PDF Document: {filename}",
            page_number=1,
        )

        # Create page-based L1 entries (group pages if many)
        l1_items: List[HierarchyNode] = []
        if page_count <= 10:
            for i in range(1, page_count + 1):
                l1_items.append(
                    HierarchyNode(
                        id=f"page_{i}",
                        title=f"Page {i}",
                        type=NodeType.TOC_ENTRY,
                        level=1,
                        page_number=i,
                        parent_id="root",
                    )
                )
        else:
            # Group into sections of ~10 pages
            section_size = max(1, page_count // 10)
            for i in range(0, page_count, section_size):
                start_page = i + 1
                end_page = min(i + section_size, page_count)
                l1_items.append(
                    HierarchyNode(
                        id=f"section_{i}",
                        title=f"Pages {start_page}-{end_page}",
                        type=NodeType.TOC_ENTRY,
                        level=1,
                        page_number=start_page,
                        parent_id="root",
                        metadata={"page_range": [start_page, end_page]},
                    )
                )

        return HierarchyTree(
            L0=HierarchyLevel(
                title=doc_title,
                description="Document root",
                items=[root_node],
            ),
            L1=HierarchyLevel(
                title="Pages",
                description="Page-based organization (no structure detected)",
                items=l1_items,
            ),
            L2=HierarchyLevel(
                title="Subsections",
                description="No subsections detected",
                items=[],
            ),
            L3=HierarchyLevel(
                title="Details",
                description="No details detected",
                items=[],
            ),
            L4=HierarchyLevel(
                title="Fine-grained Elements",
                description="No fine-grained elements detected",
                items=[],
            ),
            extraction_method=ExtractionMethod.FALLBACK,
            source_filename=filename,
            source_mime_type=source_mime_type,
            total_nodes=1 + len(l1_items),
            max_depth=1,
            extracted_at=datetime.utcnow(),
            confidence_score=0.3,  # Low confidence for fallback
            warnings=[
                "No TOC or structure detected in PDF",
                "Using page-based organization",
            ],
        )

    def _clean_filename(self, filename: str) -> str:
        """Clean filename for use as title.

        Args:
            filename: Raw filename

        Returns:
            Cleaned title string
        """
        # Remove extension
        name = filename.rsplit(".", 1)[0] if "." in filename else filename
        # Replace underscores and hyphens with spaces
        name = name.replace("_", " ").replace("-", " ")
        # Title case
        return name.title()

    @staticmethod
    def validate_structure(hierarchy: HierarchyTree) -> Tuple[bool, List[str]]:
        """Validate extracted hierarchy and return issues found.

        Args:
            hierarchy: Extracted hierarchy structure

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues: List[str] = []

        # Check root level
        if not hierarchy.L0.items:
            issues.append("Document missing root node")

        # Check for meaningful content
        if not hierarchy.L1.has_meaningful_content():
            issues.append("No meaningful L1 content extracted from PDF")

        # Include extraction warnings
        issues.extend(hierarchy.warnings)

        # Check confidence score
        if hierarchy.confidence_score < 0.5:
            issues.append(f"Low extraction confidence: {hierarchy.confidence_score:.2f}")

        return len(issues) == 0, issues
