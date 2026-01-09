"""Tests for file validation utilities."""

import pytest

from app.utils.file_validation import (
    FileValidationError,
    get_mime_type,
    validate_file_size,
    validate_file_type,
)


class TestValidateFileType:
    """Test file type validation by magic numbers."""

    @pytest.mark.asyncio
    async def test_pdf_signature_valid(self):
        """Test PDF file detection via magic number."""
        pdf_content = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
        file_type = await validate_file_type(pdf_content, "document.pdf")
        assert file_type == "pdf"

    @pytest.mark.asyncio
    async def test_markdown_header_signature(self):
        """Test markdown file detection via header signature."""
        md_content = b"# Project Documentation\n\nThis is a test."
        file_type = await validate_file_type(md_content, "README.md")
        assert file_type == "markdown"

    @pytest.mark.asyncio
    async def test_markdown_list_signature(self):
        """Test markdown file detection via list signature."""
        md_content = b"- Item 1\n- Item 2\n- Item 3"
        file_type = await validate_file_type(md_content, "notes.md")
        assert file_type == "markdown"

    @pytest.mark.asyncio
    async def test_markdown_code_block_signature(self):
        """Test markdown file detection via code block signature."""
        md_content = b"```python\nprint('hello')\n```"
        file_type = await validate_file_type(md_content, "example.md")
        assert file_type == "markdown"

    @pytest.mark.asyncio
    async def test_markdown_txt_extension_with_text(self):
        """Test plain text file detection as markdown."""
        text_content = b"This is plain text content.\nMultiple lines.\n"
        file_type = await validate_file_type(text_content, "notes.txt")
        assert file_type == "markdown"

    @pytest.mark.asyncio
    async def test_invalid_file_type_raises_error(self):
        """Test that invalid file types raise FileValidationError."""
        # Binary content that's not PDF or markdown
        binary_content = b"\x89PNG\r\n\x1a\n"  # PNG signature
        with pytest.raises(FileValidationError) as exc_info:
            await validate_file_type(binary_content, "image.png")
        assert "Unsupported file type" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_wrong_extension_but_valid_pdf(self):
        """Test PDF detection works even with wrong extension."""
        pdf_content = b"%PDF-1.7\n"
        file_type = await validate_file_type(pdf_content, "document.txt")
        assert file_type == "pdf"

    @pytest.mark.asyncio
    async def test_empty_file_raises_error(self):
        """Test that empty files raise FileValidationError."""
        empty_content = b""
        with pytest.raises(FileValidationError):
            await validate_file_type(empty_content, "empty.md")


class TestValidateFileSize:
    """Test file size validation."""

    @pytest.mark.asyncio
    async def test_markdown_within_limit(self):
        """Test markdown file within size limit passes."""
        file_size = 1 * 1024 * 1024  # 1 MB
        await validate_file_size(file_size, "markdown")  # Should not raise

    @pytest.mark.asyncio
    async def test_pdf_within_limit(self):
        """Test PDF file within size limit passes."""
        file_size = 5 * 1024 * 1024  # 5 MB
        await validate_file_size(file_size, "pdf")  # Should not raise

    @pytest.mark.asyncio
    async def test_markdown_exceeds_limit(self):
        """Test markdown file exceeding 5MB limit raises error."""
        file_size = 6 * 1024 * 1024  # 6 MB
        with pytest.raises(FileValidationError) as exc_info:
            await validate_file_size(file_size, "markdown")
        assert "exceeds maximum" in str(exc_info.value)
        assert "5 MB" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_pdf_exceeds_limit(self):
        """Test PDF file exceeding 10MB limit raises error."""
        file_size = 11 * 1024 * 1024  # 11 MB
        with pytest.raises(FileValidationError) as exc_info:
            await validate_file_size(file_size, "pdf")
        assert "exceeds maximum" in str(exc_info.value)
        assert "10 MB" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_markdown_at_exact_limit(self):
        """Test markdown file at exactly 5MB limit passes."""
        file_size = 5 * 1024 * 1024  # Exactly 5 MB
        await validate_file_size(file_size, "markdown")  # Should not raise

    @pytest.mark.asyncio
    async def test_pdf_at_exact_limit(self):
        """Test PDF file at exactly 10MB limit passes."""
        file_size = 10 * 1024 * 1024  # Exactly 10 MB
        await validate_file_size(file_size, "pdf")  # Should not raise


class TestGetMimeType:
    """Test MIME type retrieval."""

    def test_pdf_mime_type(self):
        """Test PDF MIME type."""
        mime_type = get_mime_type("pdf")
        assert mime_type == "application/pdf"

    def test_markdown_mime_type(self):
        """Test markdown MIME type."""
        mime_type = get_mime_type("markdown")
        assert mime_type == "text/markdown"
