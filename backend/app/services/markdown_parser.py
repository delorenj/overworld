"""Markdown parser service for hierarchical structure extraction."""

import re
from typing import Dict, List, Tuple

from app.schemas.document import HierarchyNode


class MarkdownParser:
    """Parser for markdown documents that extracts hierarchical structure."""

    @staticmethod
    def extract_hierarchy(markdown_content: str, filename: str) -> Dict:
        """
        Extract hierarchical L0-L4 structure from markdown content.

        Args:
            markdown_content: Raw markdown text
            filename: Original filename for context

        Returns:
            Dictionary with L0-L4 hierarchy structure
        """
        lines = markdown_content.strip().split("\n")
        hierarchy = {
            "level_0": {"title": filename, "description": "Document root"},
            "level_1": {"title": "Main Sections", "items": []},
            "level_2": {"title": "Subsections", "items": []},
            "level_3": {"title": "Details", "items": []},
            "level_4": {"title": "Fine-grained Elements", "items": []},
        }

        current_level_0 = None
        current_level_1 = None
        current_level_2 = None
        current_level_3 = None

        for line_num, line in enumerate(lines):
            line = line.strip()

            # Skip empty lines and code blocks
            if not line or line.startswith("```"):
                continue

            # Detect headers (ATX-style: #, ##, ###, ####)
            if line.startswith("#"):
                level = len(line) - len(line.lstrip("#"))
                title = line.lstrip("# ").strip()

                if level == 1:
                    current_level_0 = title
                elif level == 2:
                    current_level_1 = title
                elif level == 3:
                    current_level_2 = title
                elif level == 4:
                    current_level_3 = title

                # Store header in appropriate level
                if level == 1 and current_level_0:
                    hierarchy["level_1"]["items"].append(
                        {"type": "header", "content": title, "line": line_num}
                    )
                elif level == 2 and current_level_1:
                    hierarchy["level_2"]["items"].append(
                        {"type": "header", "content": title, "line": line_num}
                    )
                elif level == 3 and current_level_1:
                    hierarchy["level_3"]["items"].append(
                        {"type": "header", "content": title, "line": line_num}
                    )
                elif level == 4 and current_level_1:
                    hierarchy["level_4"]["items"].append(
                        {"type": "header", "content": title, "line": line_num}
                    )

            # Detect list items (-, *, +)
            elif re.match(r"^\s*[-+*]\s", line):
                item_content = line.strip("-+* ").strip()
                if item_content:
                    if current_level_1:
                        hierarchy["level_1"]["items"].append(
                            {"type": "list_item", "content": item_content, "line": line_num}
                        )
                    elif current_level_2:
                        hierarchy["level_2"]["items"].append(
                            {"type": "list_item", "content": item_content, "line": line_num}
                        )
                    elif current_level_3:
                        hierarchy["level_3"]["items"].append(
                            {"type": "list_item", "content": item_content, "line": line_num}
                        )
                    elif current_level_4:
                        hierarchy["level_4"]["items"].append(
                            {"type": "list_item", "content": item_content, "line": line_num}
                        )

            # Detect code blocks
            elif line.startswith("```"):
                if current_level_1:
                    hierarchy["level_1"]["items"].append(
                        {"type": "code_block", "language": "text", "content": "", "line": line_num}
                    )
                elif current_level_2:
                    hierarchy["level_2"]["items"].append(
                        {"type": "code_block", "language": "text", "content": "", "line": line_num}
                    )

        # Clean up empty levels
        for level in ["level_1", "level_2", "level_3", "level_4"]:
            if not hierarchy[level]["items"]:
                hierarchy[level]["items"] = [
                    {"type": "empty", "content": "No content found", "line": 0}
                ]

        return hierarchy

    @staticmethod
    def validate_structure(hierarchy: Dict) -> Tuple[bool, List[str]]:
        """
        Validate extracted hierarchy and return issues found.

        Args:
            hierarchy: Extracted hierarchy structure

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        # Check if root level has content
        if not hierarchy.get("level_0", {}).get("title"):
            issues.append("Document missing root title")

        # Check if there's meaningful content in each level
        for level_num in range(1, 5):
            level_key = f"level_{level_num}"
            level_data = hierarchy.get(level_key, {})
            items = level_data.get("items", [])

            if not items:
                issues.append(f"Level {level_num} has no content")
            else:
                # Check for at least some meaningful content
                meaningful_items = [
                    item
                    for item in items
                    if item.get("type") in ["header", "list_item"] and item.get("content")
                ]

                if not meaningful_items:
                    issues.append(f"Level {level_num} lacks meaningful content")

        # Check if hierarchy follows logical flow
        if (
            hierarchy.get("level_1", {}).get("items")
            and not hierarchy.get("level_2", {}).get("items")
            and not hierarchy.get("level_3", {}).get("items")
        ):
            issues.append("Hierarchy missing intermediate levels (L1→L3 without L2)")

        return len(issues) == 0, issues
