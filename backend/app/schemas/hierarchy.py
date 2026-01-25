"""Pydantic schemas for document hierarchy extraction.

This module defines the data models for representing hierarchical document
structure extracted from markdown and PDF documents. The hierarchy follows
an L0-L4 level structure compatible with the map generation pipeline.

L0: Root/Document level (single node)
L1: Main sections/milestones (H1 headers or top-level TOC entries)
L2: Subsections/epics (H2 headers or nested TOC entries)
L3: Details/tasks (H3 headers or deeply nested entries)
L4: Fine-grained elements/subtasks (H4+ headers or leaf entries)
"""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class NodeType(str, Enum):
    """Types of nodes in the hierarchy tree."""

    ROOT = "root"
    HEADER = "header"
    LIST_ITEM = "list_item"
    PARAGRAPH = "paragraph"
    CODE_BLOCK = "code_block"
    TABLE = "table"
    TOC_ENTRY = "toc_entry"
    AI_INFERRED = "ai_inferred"
    EMPTY = "empty"


class ExtractionMethod(str, Enum):
    """Method used to extract hierarchy."""

    MARKDOWN_PARSER = "markdown_parser"
    PDF_TOC = "pdf_toc"
    PDF_STRUCTURE = "pdf_structure"
    AI_INFERENCE = "ai_inference"
    FALLBACK = "fallback"


class HierarchyNode(BaseModel):
    """Represents a single node in the document hierarchy.

    Each node contains content information and metadata about its position
    in the document structure. Nodes can be nested to form a tree.
    """

    model_config = ConfigDict(frozen=False)

    id: str = Field(..., description="Unique identifier for this node within the document")
    title: str = Field(..., description="Display title or heading text")
    type: NodeType = Field(..., description="Type of content this node represents")
    level: int = Field(..., ge=0, le=4, description="Hierarchy level (0-4)")
    content: Optional[str] = Field(None, description="Full text content of this node")
    line_number: Optional[int] = Field(None, ge=0, description="Source line number (1-indexed)")
    page_number: Optional[int] = Field(None, ge=1, description="Source page number (for PDFs)")
    parent_id: Optional[str] = Field(None, description="ID of parent node")
    children_ids: List[str] = Field(default_factory=list, description="IDs of child nodes")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")

    def __repr__(self) -> str:
        return f"<HierarchyNode(id={self.id}, title={self.title[:30]}..., level={self.level})>"


class HierarchyLevel(BaseModel):
    """Represents a single level in the hierarchy with its items.

    This structure groups all nodes at a particular level for easier
    processing by downstream agents.
    """

    model_config = ConfigDict(frozen=False)

    title: str = Field(..., description="Display name for this level")
    description: Optional[str] = Field(None, description="Description of this level's contents")
    items: List[HierarchyNode] = Field(default_factory=list, description="Nodes at this level")

    @property
    def count(self) -> int:
        """Number of items at this level."""
        return len(self.items)

    def has_meaningful_content(self) -> bool:
        """Check if level has meaningful content (not just empty placeholders)."""
        meaningful_types = {NodeType.HEADER, NodeType.LIST_ITEM, NodeType.TOC_ENTRY}
        return any(item.type in meaningful_types and item.title for item in self.items)


class HierarchyTree(BaseModel):
    """Complete hierarchical structure extracted from a document.

    This is the primary output format for hierarchy extraction, containing
    all levels (L0-L4) and metadata about the extraction process.
    """

    model_config = ConfigDict(frozen=False)

    # Hierarchy levels
    L0: HierarchyLevel = Field(..., description="Root level (document)")
    L1: HierarchyLevel = Field(..., description="Main sections/milestones")
    L2: HierarchyLevel = Field(..., description="Subsections/epics")
    L3: HierarchyLevel = Field(..., description="Details/tasks")
    L4: HierarchyLevel = Field(..., description="Fine-grained elements/subtasks")

    # Extraction metadata
    extraction_method: ExtractionMethod = Field(
        ..., description="Method used to extract hierarchy"
    )
    source_filename: str = Field(..., description="Original source filename")
    source_mime_type: str = Field(..., description="MIME type of source document")
    total_nodes: int = Field(..., ge=0, description="Total number of nodes across all levels")
    max_depth: int = Field(..., ge=0, le=4, description="Maximum depth reached in hierarchy")
    extracted_at: datetime = Field(
        default_factory=datetime.utcnow, description="Extraction timestamp"
    )
    confidence_score: float = Field(
        default=1.0, ge=0.0, le=1.0, description="Confidence in extraction quality"
    )
    warnings: List[str] = Field(default_factory=list, description="Warnings during extraction")

    def to_legacy_format(self) -> Dict[str, Any]:
        """Convert to legacy format expected by ParserAgent.

        Returns:
            Dictionary with level_0 through level_4 keys for backward compatibility.
        """
        return {
            "level_0": {
                "title": self.L0.title,
                "description": self.L0.description,
            },
            "level_1": {
                "title": self.L1.title,
                "items": [
                    {
                        "type": item.type.value,
                        "content": item.title,
                        "line": item.line_number or 0,
                    }
                    for item in self.L1.items
                ],
            },
            "level_2": {
                "title": self.L2.title,
                "items": [
                    {
                        "type": item.type.value,
                        "content": item.title,
                        "line": item.line_number or 0,
                    }
                    for item in self.L2.items
                ],
            },
            "level_3": {
                "title": self.L3.title,
                "items": [
                    {
                        "type": item.type.value,
                        "content": item.title,
                        "line": item.line_number or 0,
                    }
                    for item in self.L3.items
                ],
            },
            "level_4": {
                "title": self.L4.title,
                "items": [
                    {
                        "type": item.type.value,
                        "content": item.title,
                        "line": item.line_number or 0,
                    }
                    for item in self.L4.items
                ],
            },
        }

    def to_agent_format(self) -> Dict[str, Any]:
        """Convert to format expected by multi-agent pipeline (L0-L4 keys).

        Returns:
            Dictionary with L0-L4 keys containing milestone data.
        """
        result: Dict[str, Any] = {"L0": None, "L1": [], "L2": [], "L3": [], "L4": []}

        # L0 - Root node
        if self.L0.items:
            root = self.L0.items[0]
            result["L0"] = {
                "id": root.id,
                "title": root.title,
                "description": root.content or self.L0.description,
            }

        # L1-L4 - Milestone lists
        for level_key, level_obj in [
            ("L1", self.L1),
            ("L2", self.L2),
            ("L3", self.L3),
            ("L4", self.L4),
        ]:
            for item in level_obj.items:
                result[level_key].append(
                    {
                        "id": item.id,
                        "title": item.title,
                        "content": item.content,
                        "parent_id": item.parent_id,
                        "metadata": item.metadata,
                    }
                )

        return result

    def get_statistics(self) -> Dict[str, Any]:
        """Get extraction statistics.

        Returns:
            Dictionary with counts and metrics about the hierarchy.
        """
        level_counts = {
            "L0": self.L0.count,
            "L1": self.L1.count,
            "L2": self.L2.count,
            "L3": self.L3.count,
            "L4": self.L4.count,
        }

        return {
            "total_nodes": self.total_nodes,
            "max_depth": self.max_depth,
            "nodes_by_level": level_counts,
            "extraction_method": self.extraction_method.value,
            "confidence_score": self.confidence_score,
            "has_warnings": len(self.warnings) > 0,
            "warning_count": len(self.warnings),
        }


class ExtractionResult(BaseModel):
    """Result of hierarchy extraction operation.

    Wraps the HierarchyTree with additional status information.
    """

    model_config = ConfigDict(frozen=False)

    success: bool = Field(..., description="Whether extraction succeeded")
    hierarchy: Optional[HierarchyTree] = Field(None, description="Extracted hierarchy tree")
    error: Optional[str] = Field(None, description="Error message if extraction failed")
    processing_time_ms: int = Field(..., ge=0, description="Processing time in milliseconds")

    @classmethod
    def failure(cls, error: str, processing_time_ms: int = 0) -> "ExtractionResult":
        """Create a failure result."""
        return cls(
            success=False,
            hierarchy=None,
            error=error,
            processing_time_ms=processing_time_ms,
        )


class HierarchyExtractionRequest(BaseModel):
    """Request schema for hierarchy extraction endpoint."""

    document_id: UUID = Field(..., description="ID of document to extract hierarchy from")
    force_reprocess: bool = Field(
        False, description="Force re-extraction even if already processed"
    )
    use_ai_fallback: bool = Field(
        True, description="Use AI inference if structured extraction fails"
    )


class HierarchyExtractionResponse(BaseModel):
    """Response schema for hierarchy extraction endpoint."""

    model_config = ConfigDict(from_attributes=True)

    document_id: UUID = Field(..., description="ID of processed document")
    status: str = Field(..., description="Processing status")
    hierarchy: Optional[Dict[str, Any]] = Field(None, description="Extracted hierarchy in L0-L4 format")
    statistics: Optional[Dict[str, Any]] = Field(None, description="Extraction statistics")
    processing_time_ms: int = Field(..., description="Processing time in milliseconds")
    error: Optional[str] = Field(None, description="Error message if extraction failed")
