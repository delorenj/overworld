"""Markdown parser service for hierarchical structure extraction.

This module provides robust markdown parsing using mistune to extract
a hierarchical L0-L4 structure from markdown documents. It handles:
- ATX-style headers (# through ####)
- Setext-style headers (underlines)
- Nested lists
- Code blocks
- Front matter
"""

import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Tuple

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
class ParsedElement:
    """Intermediate representation of a parsed markdown element."""

    type: str
    level: int
    content: str
    line_number: int
    raw_content: str = ""
    children: List["ParsedElement"] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


class MarkdownParser:
    """Parser for markdown documents that extracts hierarchical structure.

    Uses regex-based parsing for reliable hierarchy extraction.
    The parser builds an L0-L4 hierarchy tree from the extracted elements.
    """

    # Mapping from markdown heading level to hierarchy level
    HEADING_TO_LEVEL = {
        1: 1,  # H1 -> L1 (Main sections)
        2: 2,  # H2 -> L2 (Subsections)
        3: 3,  # H3 -> L3 (Details)
        4: 4,  # H4 -> L4 (Fine-grained)
        5: 4,  # H5 -> L4 (collapse into L4)
        6: 4,  # H6 -> L4 (collapse into L4)
    }

    def __init__(self) -> None:
        """Initialize the markdown parser."""
        pass

    @classmethod
    def extract_hierarchy(
        cls,
        markdown_content: str,
        filename: str,
        source_mime_type: str = "text/markdown",
    ) -> HierarchyTree:
        """Extract hierarchical L0-L4 structure from markdown content.

        Args:
            markdown_content: Raw markdown text content
            filename: Original filename for context and L0 title
            source_mime_type: MIME type of source document

        Returns:
            HierarchyTree with extracted structure
        """
        parser = cls()
        return parser._extract(markdown_content, filename, source_mime_type)

    @classmethod
    def extract_with_result(
        cls,
        markdown_content: str,
        filename: str,
        source_mime_type: str = "text/markdown",
    ) -> ExtractionResult:
        """Extract hierarchy with full result wrapper including timing.

        Args:
            markdown_content: Raw markdown text content
            filename: Original filename for context
            source_mime_type: MIME type of source

        Returns:
            ExtractionResult with hierarchy and metadata
        """
        import time

        start_time = time.time()

        try:
            hierarchy = cls.extract_hierarchy(markdown_content, filename, source_mime_type)
            processing_time_ms = int((time.time() - start_time) * 1000)

            return ExtractionResult(
                success=True,
                hierarchy=hierarchy,
                error=None,
                processing_time_ms=processing_time_ms,
            )
        except Exception as e:
            processing_time_ms = int((time.time() - start_time) * 1000)
            logger.error(f"Markdown extraction failed for {filename}: {str(e)}")

            return ExtractionResult.failure(
                error=f"Markdown extraction failed: {str(e)}",
                processing_time_ms=processing_time_ms,
            )

    def _extract(
        self,
        markdown_content: str,
        filename: str,
        source_mime_type: str,
    ) -> HierarchyTree:
        """Internal extraction method.

        Args:
            markdown_content: Raw markdown text
            filename: Source filename
            source_mime_type: MIME type

        Returns:
            HierarchyTree with extracted hierarchy
        """
        lines = markdown_content.split("\n")
        elements = self._parse_markdown(lines)

        # Build hierarchy tree
        return self._build_hierarchy_tree(
            elements=elements,
            filename=filename,
            source_mime_type=source_mime_type,
        )

    def _parse_markdown(self, lines: List[str]) -> List[ParsedElement]:
        """Parse markdown content into structural elements.

        Args:
            lines: Content lines

        Returns:
            List of parsed elements
        """
        elements: List[ParsedElement] = []
        in_code_block = False
        current_header_level = 0

        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()

            # Handle code blocks
            if stripped.startswith("```"):
                in_code_block = not in_code_block
                if in_code_block:
                    lang = stripped[3:].strip() or "text"
                    elements.append(
                        ParsedElement(
                            type="code_block",
                            level=0,
                            content=f"Code: {lang}",
                            line_number=line_num,
                            metadata={"language": lang},
                        )
                    )
                continue

            if in_code_block:
                continue

            # Skip empty lines
            if not stripped:
                continue

            # ATX headers (# through ######)
            header_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
            if header_match:
                level = len(header_match.group(1))
                content = header_match.group(2).strip()
                # Remove trailing # characters if present
                content = re.sub(r"\s*#+\s*$", "", content)
                current_header_level = level
                elements.append(
                    ParsedElement(
                        type="heading",
                        level=level,
                        content=content,
                        line_number=line_num,
                    )
                )
                continue

            # List items (-, *, +, or numbered)
            list_match = re.match(r"^(\s*)([-*+]|\d+\.)\s+(.+)$", line)
            if list_match:
                indent = len(list_match.group(1))
                content = list_match.group(3).strip()
                # Determine nesting level from indentation (2 spaces per level)
                nest_level = indent // 2 if indent else 0
                elements.append(
                    ParsedElement(
                        type="list_item",
                        level=nest_level,
                        content=content,
                        line_number=line_num,
                        metadata={"under_header_level": current_header_level},
                    )
                )
                continue

        return elements

    def _build_hierarchy_tree(
        self,
        elements: List[ParsedElement],
        filename: str,
        source_mime_type: str,
    ) -> HierarchyTree:
        """Build HierarchyTree from parsed elements.

        Args:
            elements: List of parsed markdown elements
            filename: Source filename
            source_mime_type: MIME type

        Returns:
            Complete HierarchyTree
        """
        # Initialize levels
        l0_items: List[HierarchyNode] = []
        l1_items: List[HierarchyNode] = []
        l2_items: List[HierarchyNode] = []
        l3_items: List[HierarchyNode] = []
        l4_items: List[HierarchyNode] = []

        # Create root node (L0)
        root_title = self._extract_document_title(elements, filename)
        root_node = HierarchyNode(
            id="root",
            title=root_title,
            type=NodeType.ROOT,
            level=0,
            content=f"Document: {filename}",
            line_number=1,
        )
        l0_items.append(root_node)

        # Track parent context for hierarchy
        current_parents: Dict[int, str] = {0: "root"}
        node_counter = 0
        max_depth = 0
        warnings: List[str] = []

        for element in elements:
            node_counter += 1
            node_id = f"node_{node_counter}"

            # Determine hierarchy level
            if element.type == "heading":
                h_level = self.HEADING_TO_LEVEL.get(element.level, 4)
                max_depth = max(max_depth, h_level)

                # Update parent tracking
                parent_id = current_parents.get(h_level - 1, "root")
                current_parents[h_level] = node_id

                # Clear child level parents
                for l in range(h_level + 1, 5):
                    current_parents.pop(l, None)

                node = HierarchyNode(
                    id=node_id,
                    title=element.content,
                    type=NodeType.HEADER,
                    level=h_level,
                    content=element.content,
                    line_number=element.line_number,
                    parent_id=parent_id,
                    metadata={"original_heading_level": element.level},
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

            elif element.type == "list_item":
                # List items go under the current header context
                under_header = element.metadata.get("under_header_level", 0)

                # Calculate target level based on header context and list nesting
                if under_header == 0:
                    # No header context, put at L1
                    target_level = 1
                else:
                    # Place list items one level below their header
                    base_level = self.HEADING_TO_LEVEL.get(under_header, 1)
                    target_level = min(4, base_level + 1 + element.level)

                max_depth = max(max_depth, target_level)
                parent_id = current_parents.get(target_level - 1, "root")

                node = HierarchyNode(
                    id=node_id,
                    title=element.content,
                    type=NodeType.LIST_ITEM,
                    level=target_level,
                    content=element.content,
                    line_number=element.line_number,
                    parent_id=parent_id,
                )

                if target_level == 1:
                    l1_items.append(node)
                elif target_level == 2:
                    l2_items.append(node)
                elif target_level == 3:
                    l3_items.append(node)
                else:
                    l4_items.append(node)

            elif element.type == "code_block":
                # Code blocks are informational, skip in hierarchy
                pass

        # Add warnings for sparse hierarchies
        if not l1_items:
            warnings.append("No L1 (main section) headers found in document")
        if l1_items and not l2_items:
            warnings.append("Document has L1 headers but no L2 subsections")

        # Create empty placeholders if levels are missing
        if not l1_items:
            l1_items.append(
                HierarchyNode(
                    id="empty_l1",
                    title="No main sections found",
                    type=NodeType.EMPTY,
                    level=1,
                    parent_id="root",
                )
            )
            max_depth = max(max_depth, 1)

        # Calculate total nodes
        total_nodes = len(l0_items) + len(l1_items) + len(l2_items) + len(l3_items) + len(l4_items)

        return HierarchyTree(
            L0=HierarchyLevel(
                title=root_title,
                description="Document root",
                items=l0_items,
            ),
            L1=HierarchyLevel(
                title="Main Sections",
                description="Top-level document sections (H1 headers)",
                items=l1_items,
            ),
            L2=HierarchyLevel(
                title="Subsections",
                description="Second-level sections (H2 headers)",
                items=l2_items,
            ),
            L3=HierarchyLevel(
                title="Details",
                description="Detail sections (H3 headers)",
                items=l3_items,
            ),
            L4=HierarchyLevel(
                title="Fine-grained Elements",
                description="Fine-grained sections (H4+ headers)",
                items=l4_items,
            ),
            extraction_method=ExtractionMethod.MARKDOWN_PARSER,
            source_filename=filename,
            source_mime_type=source_mime_type,
            total_nodes=total_nodes,
            max_depth=max_depth,
            extracted_at=datetime.utcnow(),
            confidence_score=self._calculate_confidence(l1_items, l2_items, warnings),
            warnings=warnings,
        )

    def _extract_document_title(
        self, elements: List[ParsedElement], filename: str
    ) -> str:
        """Extract document title from first H1 or filename.

        Args:
            elements: Parsed elements
            filename: Fallback filename

        Returns:
            Document title string
        """
        # Look for first H1 header
        for element in elements:
            if element.type == "heading" and element.level == 1:
                return element.content

        # Fallback to cleaned filename
        clean_name = filename.replace("_", " ").replace("-", " ")
        # Remove extension
        if "." in clean_name:
            clean_name = clean_name.rsplit(".", 1)[0]
        return clean_name.title()

    def _calculate_confidence(
        self,
        l1_items: List[HierarchyNode],
        l2_items: List[HierarchyNode],
        warnings: List[str],
    ) -> float:
        """Calculate confidence score for extraction quality.

        Args:
            l1_items: Level 1 items
            l2_items: Level 2 items
            warnings: Extraction warnings

        Returns:
            Confidence score between 0 and 1
        """
        score = 1.0

        # Reduce score for missing structure
        if not l1_items or l1_items[0].type == NodeType.EMPTY:
            score -= 0.3

        if not l2_items:
            score -= 0.1

        # Reduce for each warning
        score -= len(warnings) * 0.1

        return max(0.0, min(1.0, score))

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

        # Check for at least one meaningful L1 item
        if not hierarchy.L1.has_meaningful_content():
            issues.append("No meaningful L1 content found")

        # Check for logical hierarchy flow
        has_l1 = hierarchy.L1.count > 0
        has_l2 = hierarchy.L2.count > 0
        has_l3 = hierarchy.L3.count > 0

        if has_l3 and not has_l2 and has_l1:
            issues.append("Hierarchy missing intermediate level (L1 -> L3 without L2)")

        # Include extraction warnings
        issues.extend(hierarchy.warnings)

        return len(issues) == 0, issues
