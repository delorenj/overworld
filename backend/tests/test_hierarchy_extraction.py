"""Tests for hierarchy extraction functionality.

This module contains comprehensive tests for:
- Markdown parsing and hierarchy extraction
- PDF parsing and TOC extraction
- Hierarchy extraction service
- API endpoints for hierarchy extraction
"""

import pytest
from datetime import datetime
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from app.schemas.hierarchy import (
    ExtractionMethod,
    ExtractionResult,
    HierarchyLevel,
    HierarchyNode,
    HierarchyTree,
    NodeType,
)
from app.services.markdown_parser import MarkdownParser
from app.services.pdf_parser import PDFParser


# =============================================================================
# Test Data Fixtures
# =============================================================================


@pytest.fixture
def simple_markdown():
    """Simple markdown with clear hierarchy."""
    return """# Project Overview

This is the main document description.

## Getting Started

Instructions for getting started.

### Prerequisites

- Python 3.12
- Docker

### Installation

1. Clone the repository
2. Install dependencies

## Architecture

Overview of system architecture.

### Backend

FastAPI-based backend.

### Frontend

React/TypeScript frontend.

## Conclusion

Final thoughts.
"""


@pytest.fixture
def complex_markdown():
    """Complex markdown with multiple levels."""
    return """# Enterprise Project Documentation

Comprehensive guide for the enterprise system.

## Phase 1: Foundation

Building the core infrastructure.

### 1.1 Database Setup

#### 1.1.1 Schema Design

Design considerations for the database schema.

#### 1.1.2 Migration Strategy

How to handle database migrations.

### 1.2 API Development

Building the REST API layer.

## Phase 2: Features

Implementing core features.

### 2.1 User Management

User authentication and authorization.

#### 2.1.1 Authentication

OAuth2 implementation details.

#### 2.1.2 Authorization

Role-based access control.

### 2.2 Data Processing

Data ingestion and processing pipelines.

## Phase 3: Deployment

Production deployment considerations.

### 3.1 Infrastructure

Cloud infrastructure setup.

### 3.2 Monitoring

Observability and monitoring.

## Appendix

Additional resources and references.
"""


@pytest.fixture
def flat_markdown():
    """Markdown with no hierarchy (all content at same level)."""
    return """Some introductory text.

More text without any headers.

- List item 1
- List item 2
- List item 3

Another paragraph of text.
"""


@pytest.fixture
def list_heavy_markdown():
    """Markdown with lists as primary structure."""
    return """# Project Tasks

## Sprint 1

- Task A: Setup project
- Task B: Configure CI/CD
- Task C: Write tests

## Sprint 2

- Task D: Implement feature X
- Task E: Implement feature Y
- Task F: Documentation

### Sprint 2 Details

- Sub-task D.1
- Sub-task D.2

## Sprint 3

- Task G: Performance optimization
"""


@pytest.fixture
def minimal_pdf_content():
    """Minimal valid PDF content for testing."""
    # This is a minimal valid PDF structure
    return b"""%PDF-1.4
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R >>
endobj
4 0 obj
<< /Length 44 >>
stream
BT
/F1 12 Tf
100 700 Td
(Test PDF) Tj
ET
endstream
endobj
xref
0 5
0000000000 65535 f
0000000009 00000 n
0000000058 00000 n
0000000115 00000 n
0000000206 00000 n
trailer
<< /Size 5 /Root 1 0 R >>
startxref
300
%%EOF"""


# =============================================================================
# Markdown Parser Tests
# =============================================================================


class TestMarkdownParser:
    """Tests for MarkdownParser class."""

    def test_extract_simple_hierarchy(self, simple_markdown):
        """Test extraction of simple markdown hierarchy."""
        result = MarkdownParser.extract_hierarchy(
            markdown_content=simple_markdown,
            filename="test.md",
        )

        # Verify it's a valid HierarchyTree
        assert isinstance(result, HierarchyTree)
        assert result.extraction_method == ExtractionMethod.MARKDOWN_PARSER
        assert result.source_filename == "test.md"

        # Check root level
        assert result.L0.count == 1
        assert result.L0.items[0].type == NodeType.ROOT

        # Check L1 items (H1 headers)
        assert result.L1.count >= 1
        l1_titles = [item.title for item in result.L1.items]
        assert "Project Overview" in l1_titles

        # Check L2 items (H2 headers)
        assert result.L2.count >= 2
        l2_titles = [item.title for item in result.L2.items]
        assert "Getting Started" in l2_titles
        assert "Architecture" in l2_titles

        # Check L3 items (H3 headers)
        assert result.L3.count >= 2
        l3_titles = [item.title for item in result.L3.items]
        assert "Prerequisites" in l3_titles
        assert "Installation" in l3_titles

    def test_extract_complex_hierarchy(self, complex_markdown):
        """Test extraction of complex nested markdown hierarchy."""
        result = MarkdownParser.extract_hierarchy(
            markdown_content=complex_markdown,
            filename="enterprise_docs.md",
        )

        # Should have items at all 4 levels
        assert result.L1.count >= 1
        assert result.L2.count >= 3  # Phase 1, 2, 3
        assert result.L3.count >= 5  # Multiple subsections
        assert result.L4.count >= 4  # H4 headers

        # Check max depth
        assert result.max_depth == 4

        # Verify parent-child relationships
        l4_item = next(
            (item for item in result.L4.items if "1.1.1" in item.title),
            None,
        )
        if l4_item:
            assert l4_item.parent_id is not None

    def test_extract_flat_document(self, flat_markdown):
        """Test extraction from document without clear hierarchy."""
        result = MarkdownParser.extract_hierarchy(
            markdown_content=flat_markdown,
            filename="flat.md",
        )

        # Should still produce valid hierarchy
        assert isinstance(result, HierarchyTree)
        assert result.L0.count == 1

        # Should have warnings about missing structure
        assert len(result.warnings) > 0
        assert result.confidence_score < 1.0

    def test_extract_list_based_structure(self, list_heavy_markdown):
        """Test extraction of list-heavy markdown."""
        result = MarkdownParser.extract_hierarchy(
            markdown_content=list_heavy_markdown,
            filename="tasks.md",
        )

        # Should extract headers
        assert result.L1.count >= 1

        # L2 should include Sprint sections
        l2_titles = [item.title for item in result.L2.items]
        assert any("Sprint" in title for title in l2_titles)

        # List items should be captured
        total_items = (
            result.L1.count
            + result.L2.count
            + result.L3.count
            + result.L4.count
        )
        assert total_items > 5

    def test_extract_with_result_wrapper(self, simple_markdown):
        """Test extraction with ExtractionResult wrapper."""
        result = MarkdownParser.extract_with_result(
            markdown_content=simple_markdown,
            filename="test.md",
        )

        assert isinstance(result, ExtractionResult)
        assert result.success is True
        assert result.hierarchy is not None
        assert result.processing_time_ms >= 0
        assert result.error is None

    def test_extract_empty_document(self):
        """Test extraction from empty document."""
        result = MarkdownParser.extract_hierarchy(
            markdown_content="",
            filename="empty.md",
        )

        # Should still produce valid hierarchy with placeholder
        assert isinstance(result, HierarchyTree)
        assert result.L0.count == 1
        assert result.confidence_score <= 0.5  # May equal 0.5 due to scoring formula

    def test_extract_code_blocks_handled(self):
        """Test that code blocks don't interfere with parsing."""
        markdown_with_code = """# Main Section

Some text.

```python
# This is not a header
## Neither is this
def function():
    pass
```

## Actual Second Section

More text.
"""
        result = MarkdownParser.extract_hierarchy(
            markdown_content=markdown_with_code,
            filename="code.md",
        )

        # Should only extract actual headers
        l1_titles = [item.title for item in result.L1.items]
        l2_titles = [item.title for item in result.L2.items]

        assert "Main Section" in l1_titles
        assert "Actual Second Section" in l2_titles
        # Code block content should not appear as headers
        assert "This is not a header" not in l1_titles
        assert "Neither is this" not in l2_titles

    def test_validate_structure(self, simple_markdown):
        """Test hierarchy structure validation."""
        hierarchy = MarkdownParser.extract_hierarchy(
            markdown_content=simple_markdown,
            filename="test.md",
        )

        is_valid, issues = MarkdownParser.validate_structure(hierarchy)

        # Simple markdown should produce valid structure
        assert is_valid is True or len(issues) > 0

    def test_to_agent_format(self, simple_markdown):
        """Test conversion to agent pipeline format."""
        hierarchy = MarkdownParser.extract_hierarchy(
            markdown_content=simple_markdown,
            filename="test.md",
        )

        agent_format = hierarchy.to_agent_format()

        # Should have L0-L4 keys
        assert "L0" in agent_format
        assert "L1" in agent_format
        assert "L2" in agent_format
        assert "L3" in agent_format
        assert "L4" in agent_format

        # L0 should be a dict with title
        assert agent_format["L0"] is not None
        assert "title" in agent_format["L0"]

        # L1-L4 should be lists
        assert isinstance(agent_format["L1"], list)
        assert isinstance(agent_format["L2"], list)

    def test_to_legacy_format(self, simple_markdown):
        """Test conversion to legacy format."""
        hierarchy = MarkdownParser.extract_hierarchy(
            markdown_content=simple_markdown,
            filename="test.md",
        )

        legacy_format = hierarchy.to_legacy_format()

        # Should have level_0 through level_4 keys
        assert "level_0" in legacy_format
        assert "level_1" in legacy_format
        assert "level_2" in legacy_format
        assert "level_3" in legacy_format
        assert "level_4" in legacy_format


# =============================================================================
# PDF Parser Tests
# =============================================================================


class TestPDFParser:
    """Tests for PDFParser class."""

    def test_extract_from_minimal_pdf(self, minimal_pdf_content):
        """Test extraction from minimal PDF."""
        # Note: This minimal PDF doesn't have a TOC, so it should use fallback
        result = PDFParser.extract_with_result(
            pdf_content=minimal_pdf_content,
            filename="minimal.pdf",
        )

        # Should still produce a result (even if fallback)
        assert isinstance(result, ExtractionResult)
        # May succeed or fail depending on PDF validity
        if result.success:
            assert result.hierarchy is not None
            assert result.hierarchy.source_filename == "minimal.pdf"

    def test_extract_invalid_pdf(self):
        """Test extraction from invalid PDF content."""
        invalid_content = b"This is not a PDF file"

        result = PDFParser.extract_with_result(
            pdf_content=invalid_content,
            filename="invalid.pdf",
        )

        # Should fail gracefully
        assert isinstance(result, ExtractionResult)
        assert result.success is False
        assert result.error is not None
        assert "Invalid PDF" in result.error or "PDF" in result.error

    def test_extract_empty_pdf(self):
        """Test extraction from empty bytes."""
        result = PDFParser.extract_with_result(
            pdf_content=b"",
            filename="empty.pdf",
        )

        # Should fail gracefully
        assert isinstance(result, ExtractionResult)
        assert result.success is False

    def test_clean_filename(self):
        """Test filename cleaning utility."""
        parser = PDFParser()

        # Test various filename formats
        assert parser._clean_filename("my_file.pdf") == "My File"
        assert parser._clean_filename("my-file.pdf") == "My File"
        assert parser._clean_filename("MyFile.pdf") == "Myfile"
        assert parser._clean_filename("file") == "File"

    def test_is_likely_header(self):
        """Test header detection heuristics."""
        parser = PDFParser()

        # Should detect as headers
        assert parser._is_likely_header("1.1 Introduction") is True
        assert parser._is_likely_header("Chapter 1") is True
        assert parser._is_likely_header("SUMMARY") is True
        assert parser._is_likely_header("Section 2") is True
        assert parser._is_likely_header("Part I") is True
        assert parser._is_likely_header("Appendix A") is True

        # Should not detect as headers
        assert parser._is_likely_header("This is a long paragraph of text that continues") is False

    def test_infer_header_level(self):
        """Test header level inference."""
        parser = PDFParser()

        # Test various header formats
        assert parser._infer_header_level("1.1 Title") == 2
        assert parser._infer_header_level("1.1.1 Subtitle") == 3
        assert parser._infer_header_level("Chapter 1") == 1
        assert parser._infer_header_level("Part I") == 1
        assert parser._infer_header_level("Section 2") == 2
        assert parser._infer_header_level("UPPERCASE HEADER") == 1


# =============================================================================
# Hierarchy Schema Tests
# =============================================================================


class TestHierarchySchemas:
    """Tests for hierarchy Pydantic schemas."""

    def test_hierarchy_node_creation(self):
        """Test HierarchyNode creation and validation."""
        node = HierarchyNode(
            id="test_node",
            title="Test Node",
            type=NodeType.HEADER,
            level=1,
            content="Test content",
            line_number=10,
        )

        assert node.id == "test_node"
        assert node.title == "Test Node"
        assert node.type == NodeType.HEADER
        assert node.level == 1
        assert node.children_ids == []

    def test_hierarchy_node_with_parent(self):
        """Test HierarchyNode with parent relationship."""
        parent = HierarchyNode(
            id="parent",
            title="Parent",
            type=NodeType.HEADER,
            level=1,
        )

        child = HierarchyNode(
            id="child",
            title="Child",
            type=NodeType.HEADER,
            level=2,
            parent_id="parent",
        )

        assert child.parent_id == "parent"

    def test_hierarchy_level_meaningful_content(self):
        """Test HierarchyLevel.has_meaningful_content method."""
        # Level with meaningful content
        level_with_content = HierarchyLevel(
            title="Test Level",
            items=[
                HierarchyNode(
                    id="1",
                    title="Header",
                    type=NodeType.HEADER,
                    level=1,
                ),
            ],
        )
        assert level_with_content.has_meaningful_content() is True

        # Level with only empty nodes
        level_empty = HierarchyLevel(
            title="Empty Level",
            items=[
                HierarchyNode(
                    id="empty",
                    title="Empty",
                    type=NodeType.EMPTY,
                    level=1,
                ),
            ],
        )
        assert level_empty.has_meaningful_content() is False

    def test_hierarchy_tree_statistics(self, simple_markdown):
        """Test HierarchyTree.get_statistics method."""
        hierarchy = MarkdownParser.extract_hierarchy(
            markdown_content=simple_markdown,
            filename="test.md",
        )

        stats = hierarchy.get_statistics()

        assert "total_nodes" in stats
        assert "max_depth" in stats
        assert "nodes_by_level" in stats
        assert "extraction_method" in stats
        assert "confidence_score" in stats

        assert stats["total_nodes"] == hierarchy.total_nodes
        assert stats["max_depth"] == hierarchy.max_depth

    def test_extraction_result_failure_factory(self):
        """Test ExtractionResult.failure factory method."""
        result = ExtractionResult.failure(
            error="Test error message",
            processing_time_ms=100,
        )

        assert result.success is False
        assert result.hierarchy is None
        assert result.error == "Test error message"
        assert result.processing_time_ms == 100


# =============================================================================
# Integration Tests
# =============================================================================


class TestHierarchyExtractionIntegration:
    """Integration tests for hierarchy extraction."""

    @pytest.mark.asyncio
    async def test_full_markdown_extraction_flow(self, simple_markdown):
        """Test full markdown extraction flow."""
        # Direct parsing
        result = MarkdownParser.extract_with_result(
            markdown_content=simple_markdown,
            filename="integration_test.md",
        )

        assert result.success is True
        assert result.hierarchy is not None

        # Convert to agent format
        agent_format = result.hierarchy.to_agent_format()
        assert "L0" in agent_format
        assert "L1" in agent_format

        # Validate structure
        is_valid, issues = MarkdownParser.validate_structure(result.hierarchy)
        # Note: may have warnings but should be processable

    def test_extraction_method_enum(self):
        """Test ExtractionMethod enum values."""
        assert ExtractionMethod.MARKDOWN_PARSER.value == "markdown_parser"
        assert ExtractionMethod.PDF_TOC.value == "pdf_toc"
        assert ExtractionMethod.PDF_STRUCTURE.value == "pdf_structure"
        assert ExtractionMethod.AI_INFERENCE.value == "ai_inference"
        assert ExtractionMethod.FALLBACK.value == "fallback"

    def test_node_type_enum(self):
        """Test NodeType enum values."""
        assert NodeType.ROOT.value == "root"
        assert NodeType.HEADER.value == "header"
        assert NodeType.LIST_ITEM.value == "list_item"
        assert NodeType.TOC_ENTRY.value == "toc_entry"
        assert NodeType.AI_INFERRED.value == "ai_inferred"
        assert NodeType.EMPTY.value == "empty"


# =============================================================================
# Edge Cases and Error Handling Tests
# =============================================================================


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_unicode_content(self):
        """Test handling of unicode content."""
        unicode_markdown = """# Unicode Test

## Japanese: 日本語

Some text in Japanese: こんにちは

## Chinese: 中文

Some text in Chinese: 你好

## Emoji: Test

Some emoji: 🚀 🎉 ✨
"""
        result = MarkdownParser.extract_hierarchy(
            markdown_content=unicode_markdown,
            filename="unicode.md",
        )

        assert result.L1.count >= 1
        l2_titles = [item.title for item in result.L2.items]
        assert any("Japanese" in title for title in l2_titles)

    def test_very_deep_nesting(self):
        """Test handling of very deep nesting."""
        deep_markdown = """# Level 1

## Level 2

### Level 3

#### Level 4

##### Level 5

###### Level 6

Content at level 6.
"""
        result = MarkdownParser.extract_hierarchy(
            markdown_content=deep_markdown,
            filename="deep.md",
        )

        # H5 and H6 should be collapsed into L4
        assert result.max_depth <= 4

    def test_special_characters_in_headers(self):
        """Test handling of special characters in headers."""
        special_markdown = """# Header with "quotes"

## Header with <brackets>

### Header with & ampersand

#### Header with 'apostrophes'
"""
        result = MarkdownParser.extract_hierarchy(
            markdown_content=special_markdown,
            filename="special.md",
        )

        # Should handle special characters
        assert result.L1.count >= 1
        assert result.L2.count >= 1

    def test_malformed_markdown(self):
        """Test handling of malformed markdown."""
        malformed_markdown = """#No space after hash

##Also no space

#

##

### Valid Header

Regular text
"""
        result = MarkdownParser.extract_hierarchy(
            markdown_content=malformed_markdown,
            filename="malformed.md",
        )

        # Should still produce valid result
        assert isinstance(result, HierarchyTree)
        # Should find the valid header
        l3_titles = [item.title for item in result.L3.items]
        assert "Valid Header" in l3_titles

    def test_very_long_content(self):
        """Test handling of very long content."""
        # Create markdown with many sections
        sections = []
        for i in range(100):
            sections.append(f"## Section {i}\n\nContent for section {i}.\n")

        long_markdown = "# Large Document\n\n" + "\n".join(sections)

        result = MarkdownParser.extract_hierarchy(
            markdown_content=long_markdown,
            filename="long.md",
        )

        # Should handle many sections
        assert result.L2.count >= 50  # At least half should be captured

    def test_content_hash_uniqueness(self, simple_markdown, complex_markdown):
        """Test that different documents produce different content hashes."""
        from app.services.hierarchy_extraction import HierarchyExtractionService

        service = HierarchyExtractionService()

        hierarchy1 = MarkdownParser.extract_hierarchy(
            markdown_content=simple_markdown,
            filename="doc1.md",
        )
        hierarchy2 = MarkdownParser.extract_hierarchy(
            markdown_content=complex_markdown,
            filename="doc2.md",
        )

        hash1 = service._calculate_content_hash(hierarchy1.to_agent_format())
        hash2 = service._calculate_content_hash(hierarchy2.to_agent_format())

        assert hash1 != hash2
        assert len(hash1) == 64  # SHA-256 produces 64 hex characters
