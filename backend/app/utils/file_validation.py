"""File validation utilities for upload handling."""

from typing import Literal

# Magic number signatures for file type detection
PDF_SIGNATURE = b"%PDF-"
MARKDOWN_SIGNATURES = [
    b"# ",  # Markdown header
    b"## ",
    b"### ",
    b"- ",  # Markdown list
    b"* ",
    b"```",  # Code block
]

# File size limits (in bytes)
MAX_MARKDOWN_SIZE = 5 * 1024 * 1024  # 5 MB
MAX_PDF_SIZE = 10 * 1024 * 1024  # 10 MB


FileType = Literal["markdown", "pdf"]


class FileValidationError(Exception):
    """Raised when file validation fails."""

    pass


async def validate_file_type(file_content: bytes, filename: str) -> FileType:
    """
    Validate file type by checking magic numbers (file signatures).

    Args:
        file_content: First few bytes of the file content
        filename: Original filename (for fallback detection)

    Returns:
        FileType: Either "markdown" or "pdf"

    Raises:
        FileValidationError: If file type is not supported or file is empty
    """
    # Check for empty file
    if not file_content or len(file_content) == 0:
        raise FileValidationError(
            "Empty file provided. Please upload a non-empty file."
        )

    # Check for PDF signature
    if file_content.startswith(PDF_SIGNATURE):
        return "pdf"

    # Check for markdown signatures
    # Markdown files are plain text, so we check for common markdown patterns
    try:
        # Try to decode as UTF-8 (markdown should be text)
        text_content = file_content.decode("utf-8", errors="ignore")

        # Check for markdown patterns
        for signature in MARKDOWN_SIGNATURES:
            if file_content.startswith(signature):
                return "markdown"

        # Additional check: if filename ends with .md and content is decodable UTF-8
        if filename.lower().endswith((".md", ".markdown", ".txt")):
            # Verify it's actually readable text
            if text_content and len(text_content.strip()) > 0:
                return "markdown"

    except UnicodeDecodeError:
        pass

    # If we get here, file type is not supported
    raise FileValidationError(
        f"Unsupported file type. Only markdown (.md, .txt) and PDF files are accepted. "
        f"File '{filename}' does not match expected format."
    )


async def validate_file_size(file_size: int, file_type: FileType) -> None:
    """
    Validate file size against type-specific limits.

    Args:
        file_size: Size of the file in bytes
        file_type: Type of the file

    Raises:
        FileValidationError: If file size exceeds limit
    """
    if file_type == "markdown":
        max_size = MAX_MARKDOWN_SIZE
        max_size_mb = 5
    else:  # pdf
        max_size = MAX_PDF_SIZE
        max_size_mb = 10

    if file_size > max_size:
        raise FileValidationError(
            f"File size ({file_size / 1024 / 1024:.2f} MB) exceeds maximum allowed "
            f"size for {file_type} files ({max_size_mb} MB)"
        )


def get_mime_type(file_type: FileType) -> str:
    """
    Get MIME type string for file type.

    Args:
        file_type: Type of the file

    Returns:
        MIME type string
    """
    if file_type == "pdf":
        return "application/pdf"
    else:  # markdown
        return "text/markdown"
