import pytest
from typing import Dict, Any, Tuple
from app.core.md_formatter import (
    TextBlock,
    MarkdownFormatter,
    detect_heading_level,
    detect_list_item,
)


class TestTextBlock:
    """Tests for TextBlock dataclass"""

    def test_text_block_creation(self):
        """Should create TextBlock with all fields"""
        block = TextBlock(
            content="Test content",
            block_type="paragraph",
            page_num=1,
            position=(0, 0, 100, 100),
        )

        assert block.content == "Test content"
        assert block.block_type == "paragraph"
        assert block.page_num == 1
        assert block.position == (0, 0, 100, 100)

    def test_text_block_heading_type(self):
        """Should support heading block type"""
        block = TextBlock(
            content="# Heading",
            block_type="heading",
            page_num=1,
            position=(0, 0, 100, 50),
        )

        assert block.block_type == "heading"

    def test_text_block_list_item_type(self):
        """Should support list_item block type"""
        block = TextBlock(
            content="- Item",
            block_type="list_item",
            page_num=1,
            position=(0, 0, 100, 30),
        )

        assert block.block_type == "list_item"

    def test_text_block_image_type(self):
        """Should support image block type"""
        block = TextBlock(
            content="![alt](image.png)",
            block_type="image",
            page_num=1,
            position=(0, 0, 100, 100),
        )

        assert block.block_type == "image"


class TestMarkdownFormatterInit:
    """Tests for MarkdownFormatter initialization"""

    def test_formatter_init(self):
        """Should initialize with empty blocks and paragraph"""
        formatter = MarkdownFormatter()

        assert formatter.blocks == []
        assert formatter.current_paragraph == []
        assert formatter.image_references == {}

    def test_formatter_creates_new_instances(self):
        """Should create independent instances"""
        formatter1 = MarkdownFormatter()
        formatter2 = MarkdownFormatter()

        block = TextBlock(
            content="test",
            block_type="paragraph",
            page_num=1,
            position=(0, 0, 100, 30),
        )
        formatter1.blocks.append(block)
        assert formatter2.blocks == []


class TestMarkdownFormatterAddSpan:
    """Tests for add_span method"""

    def test_add_span_simple_text(self):
        """Should add simple text to paragraph"""
        formatter = MarkdownFormatter()
        span_data = {"font": "regular", "size": 12, "flags": 0}

        formatter.add_span("Hello world", span_data, 1, (0, 0, 100, 30))

        assert len(formatter.current_paragraph) == 1
        assert "Hello world" in formatter.current_paragraph[0]

    def test_add_span_empty_text_ignored(self):
        """Should ignore empty or whitespace-only text"""
        formatter = MarkdownFormatter()
        span_data = {"font": "regular", "size": 12, "flags": 0}

        formatter.add_span("", span_data, 1, (0, 0, 100, 30))
        formatter.add_span("   ", span_data, 1, (0, 0, 100, 30))

        assert len(formatter.current_paragraph) == 0

    def test_add_span_bold_text(self):
        """Should format bold text"""
        formatter = MarkdownFormatter()
        span_data = {"font": "bold", "size": 12, "flags": 16}

        formatter.add_span("Bold text", span_data, 1, (0, 0, 100, 30))

        assert "**Bold text**" in formatter.current_paragraph[0]

    def test_add_span_italic_text(self):
        """Should format italic text"""
        formatter = MarkdownFormatter()
        span_data = {"font": "italic", "size": 12, "flags": 2}

        formatter.add_span("Italic text", span_data, 1, (0, 0, 100, 30))

        assert "*Italic text*" in formatter.current_paragraph[0]

    def test_add_span_multiple_calls(self):
        """Should accumulate text in paragraph"""
        formatter = MarkdownFormatter()
        span_data = {"font": "regular", "size": 12, "flags": 0}

        formatter.add_span("Hello ", span_data, 1, (0, 0, 50, 30))
        formatter.add_span("world", span_data, 1, (50, 0, 100, 30))

        assert len(formatter.current_paragraph) == 2


class TestMarkdownFormatterEndParagraph:
    """Tests for end_paragraph method"""

    def test_end_paragraph_empty(self):
        """Should not add block if paragraph is empty"""
        formatter = MarkdownFormatter()

        formatter.end_paragraph(1)

        assert len(formatter.blocks) == 0

    def test_end_paragraph_with_content(self):
        """Should add paragraph block"""
        formatter = MarkdownFormatter()
        span_data = {"font": "regular", "size": 12, "flags": 0}

        formatter.add_span("Test paragraph", span_data, 1, (0, 0, 100, 30))
        formatter.end_paragraph(1, (0, 0, 100, 30))

        assert len(formatter.blocks) == 1
        assert formatter.blocks[0].block_type == "paragraph"
        assert "Test paragraph" in formatter.blocks[0].content

    def test_end_paragraph_clears_current(self):
        """Should clear current_paragraph after ending"""
        formatter = MarkdownFormatter()
        span_data = {"font": "regular", "size": 12, "flags": 0}

        formatter.add_span("Text", span_data, 1, (0, 0, 100, 30))
        formatter.end_paragraph(1)

        assert len(formatter.current_paragraph) == 0

    def test_end_paragraph_whitespace_only(self):
        """Should not add block if only whitespace"""
        formatter = MarkdownFormatter()
        formatter.current_paragraph = ["   ", "  \n  "]

        formatter.end_paragraph(1)

        assert len(formatter.blocks) == 0


class TestMarkdownFormatterAddHeading:
    """Tests for add_heading method"""

    def test_add_heading_level_1(self):
        """Should add level 1 heading"""
        formatter = MarkdownFormatter()

        formatter.add_heading("Title", 1, 1, (0, 0, 100, 50))

        assert len(formatter.blocks) == 1
        assert formatter.blocks[0].content == "# Title"
        assert formatter.blocks[0].block_type == "heading"

    def test_add_heading_level_2(self):
        """Should add level 2 heading"""
        formatter = MarkdownFormatter()

        formatter.add_heading("Subtitle", 2, 1, (0, 0, 100, 40))

        assert formatter.blocks[0].content == "## Subtitle"

    def test_add_heading_level_3(self):
        """Should add level 3 heading"""
        formatter = MarkdownFormatter()

        formatter.add_heading("Section", 3, 1)

        assert formatter.blocks[0].content == "### Section"

    def test_add_heading_ends_paragraph(self):
        """Should end current paragraph before adding heading"""
        formatter = MarkdownFormatter()
        span_data = {"font": "regular", "size": 12, "flags": 0}

        formatter.add_span("Previous text", span_data, 1, (0, 0, 100, 30))
        formatter.add_heading("Heading", 1, 1)

        assert len(formatter.blocks) == 2
        assert formatter.blocks[0].content == "Previous text"
        assert formatter.blocks[1].content == "# Heading"

    def test_add_heading_empty_text(self):
        """Should not add heading if text is empty"""
        formatter = MarkdownFormatter()

        formatter.add_heading("", 1, 1)
        formatter.add_heading("   ", 1, 1)

        assert len(formatter.blocks) == 0

    def test_add_heading_all_levels(self):
        """Should support heading levels 1-6"""
        formatter = MarkdownFormatter()

        for level in range(1, 7):
            formatter.add_heading(f"Level {level}", level, 1)

        assert len(formatter.blocks) == 6
        assert formatter.blocks[0].content.startswith("#")
        assert formatter.blocks[5].content.startswith("######")


class TestMarkdownFormatterAddListItem:
    """Tests for add_list_item method"""

    def test_add_list_item_level_1(self):
        """Should add level 1 list item"""
        formatter = MarkdownFormatter()

        formatter.add_list_item("First item", 1, 1)

        assert len(formatter.blocks) == 1
        assert formatter.blocks[0].content == "- First item"
        assert formatter.blocks[0].block_type == "list_item"

    def test_add_list_item_level_2(self):
        """Should add indented list item"""
        formatter = MarkdownFormatter()

        formatter.add_list_item("Nested item", 2, 1)

        assert formatter.blocks[0].content == "  - Nested item"

    def test_add_list_item_level_3(self):
        """Should add more indented list item"""
        formatter = MarkdownFormatter()

        formatter.add_list_item("Deep item", 3, 1)

        assert formatter.blocks[0].content == "    - Deep item"

    def test_add_list_item_empty_text(self):
        """Should not add list item if text is empty"""
        formatter = MarkdownFormatter()

        formatter.add_list_item("", 1, 1)
        formatter.add_list_item("   ", 1, 1)

        assert len(formatter.blocks) == 0

    def test_add_multiple_list_items(self):
        """Should add multiple list items"""
        formatter = MarkdownFormatter()

        formatter.add_list_item("Item 1", 1, 1)
        formatter.add_list_item("Item 2", 1, 1)
        formatter.add_list_item("Item 3", 1, 1)

        assert len(formatter.blocks) == 3
        assert all(b.block_type == "list_item" for b in formatter.blocks)


class TestMarkdownFormatterAddImage:
    """Tests for add_image method"""

    def test_add_image_simple(self):
        """Should add image block"""
        formatter = MarkdownFormatter()

        formatter.add_image("images/page1_img1.png", "Figure 1", 1, (0, 0, 100, 100))

        assert len(formatter.blocks) == 1
        assert formatter.blocks[0].block_type == "image"
        assert "![Figure 1](images/page1_img1.png)" in formatter.blocks[0].content

    def test_add_image_default_alt_text(self):
        """Should use default alt text"""
        formatter = MarkdownFormatter()

        formatter.add_image("images/pic.png", page_num=1)

        assert "![Imagem]" in formatter.blocks[0].content

    def test_add_image_ends_paragraph(self):
        """Should end paragraph before adding image"""
        formatter = MarkdownFormatter()
        span_data = {"font": "regular", "size": 12, "flags": 0}

        formatter.add_span("Text before image", span_data, 1, (0, 0, 100, 30))
        formatter.add_image("images/pic.png", page_num=1)

        assert len(formatter.blocks) == 2
        assert formatter.blocks[0].block_type == "paragraph"
        assert formatter.blocks[1].block_type == "image"

    def test_add_image_with_special_chars_in_path(self):
        """Should handle special characters in image path"""
        formatter = MarkdownFormatter()

        formatter.add_image("images/page-1_image_001.png", "Image with special chars", 1)

        assert "page-1_image_001.png" in formatter.blocks[0].content


class TestMarkdownFormatterAddPageBreak:
    """Tests for add_page_break method"""

    def test_add_page_break_ends_paragraph(self):
        """Should end paragraph before adding page break"""
        formatter = MarkdownFormatter()
        span_data = {"font": "regular", "size": 12, "flags": 0}

        formatter.add_span("Text", span_data, 1, (0, 0, 100, 30))
        formatter.add_page_break(1)

        assert len(formatter.blocks) == 2
        assert formatter.blocks[0].block_type == "paragraph"


class TestMarkdownFormatterGenerateMarkdown:
    """Tests for generate_markdown method"""

    def test_generate_markdown_empty(self):
        """Should generate empty string for empty formatter"""
        formatter = MarkdownFormatter()

        result = formatter.generate_markdown()

        assert result == ""

    def test_generate_markdown_single_paragraph(self):
        """Should generate markdown with single paragraph"""
        formatter = MarkdownFormatter()
        span_data = {"font": "regular", "size": 12, "flags": 0}

        formatter.add_span("Hello world", span_data, 1, (0, 0, 100, 30))
        result = formatter.generate_markdown()

        assert "Hello world" in result

    def test_generate_markdown_multiple_paragraphs(self):
        """Should generate markdown with multiple paragraphs"""
        formatter = MarkdownFormatter()
        span_data = {"font": "regular", "size": 12, "flags": 0}

        formatter.add_span("Paragraph 1", span_data, 1, (0, 0, 100, 30))
        formatter.end_paragraph(1)
        formatter.add_span("Paragraph 2", span_data, 1, (0, 0, 100, 30))

        result = formatter.generate_markdown()

        assert "Paragraph 1" in result
        assert "Paragraph 2" in result

    def test_generate_markdown_with_headings(self):
        """Should generate markdown with headings"""
        formatter = MarkdownFormatter()

        formatter.add_heading("Title", 1, 1)
        formatter.add_heading("Section", 2, 1)

        result = formatter.generate_markdown()

        assert "# Title" in result
        assert "## Section" in result

    def test_generate_markdown_with_list(self):
        """Should generate markdown with list items"""
        formatter = MarkdownFormatter()

        formatter.add_list_item("Item 1", 1, 1)
        formatter.add_list_item("Item 2", 1, 1)

        result = formatter.generate_markdown()

        assert "- Item 1" in result
        assert "- Item 2" in result

    def test_generate_markdown_with_images(self):
        """Should generate markdown with images"""
        formatter = MarkdownFormatter()

        formatter.add_image("images/pic1.png", "Figure 1", 1)
        formatter.add_image("images/pic2.png", "Figure 2", 1)

        result = formatter.generate_markdown()

        assert "![Figure 1]" in result
        assert "![Figure 2]" in result

    def test_generate_markdown_removes_multiple_breaks(self):
        """Should remove multiple consecutive line breaks"""
        formatter = MarkdownFormatter()

        formatter.blocks = [
            TextBlock("Paragraph", "paragraph", 1, (0, 0, 100, 30)),
            TextBlock("", "paragraph", 1, (0, 0, 100, 30)),
            TextBlock("", "paragraph", 1, (0, 0, 100, 30)),
            TextBlock("", "paragraph", 1, (0, 0, 100, 30)),
            TextBlock("Another", "paragraph", 1, (0, 0, 100, 30)),
        ]

        result = formatter.generate_markdown()

        # Should have max 2 consecutive newlines
        assert "\n\n\n" not in result

    def test_generate_markdown_complete_document(self):
        """Should generate complete markdown document"""
        formatter = MarkdownFormatter()

        formatter.add_heading("Main Title", 1, 1)
        formatter.add_heading("Introduction", 2, 1)
        span_data = {"font": "regular", "size": 12, "flags": 0}
        formatter.add_span("Some introduction text", span_data, 1, (0, 0, 100, 30))
        formatter.end_paragraph(1)

        formatter.add_heading("Items", 2, 1)
        formatter.add_list_item("First item", 1, 1)
        formatter.add_list_item("Second item", 1, 1)

        result = formatter.generate_markdown()

        assert "# Main Title" in result
        assert "## Introduction" in result
        assert "Some introduction text" in result
        assert "- First item" in result


class TestMarkdownFormatterSetImageReference:
    """Tests for set_image_reference method"""

    def test_set_image_reference(self):
        """Should store image reference"""
        formatter = MarkdownFormatter()

        formatter.set_image_reference("1", "images/pic1.png")

        assert formatter.image_references["1"] == "images/pic1.png"

    def test_set_multiple_image_references(self):
        """Should store multiple image references"""
        formatter = MarkdownFormatter()

        formatter.set_image_reference("1", "images/pic1.png")
        formatter.set_image_reference("2", "images/pic2.png")
        formatter.set_image_reference("3", "images/pic3.png")

        assert len(formatter.image_references) == 3
        assert formatter.image_references["2"] == "images/pic2.png"

    def test_set_image_reference_override(self):
        """Should override existing reference"""
        formatter = MarkdownFormatter()

        formatter.set_image_reference("1", "images/old.png")
        formatter.set_image_reference("1", "images/new.png")

        assert formatter.image_references["1"] == "images/new.png"


class TestDetectHeadingLevel:
    """Tests for detect_heading_level function"""

    def test_detect_heading_level_h1(self):
        """Should detect level 1 heading (large bold text)"""
        span_data = {"font": "bold", "size": 28, "flags": 16}

        result = detect_heading_level(span_data)

        assert result == 1

    def test_detect_heading_level_h2(self):
        """Should detect level 2 heading"""
        span_data = {"font": "bold", "size": 22, "flags": 16}

        result = detect_heading_level(span_data)

        assert result == 2

    def test_detect_heading_level_h3(self):
        """Should detect level 3 heading"""
        span_data = {"font": "bold", "size": 19, "flags": 16}

        result = detect_heading_level(span_data)

        assert result == 3

    def test_detect_heading_level_h4(self):
        """Should detect level 4 heading"""
        span_data = {"font": "bold", "size": 15, "flags": 16}

        result = detect_heading_level(span_data)

        assert result == 4

    def test_detect_heading_level_not_heading(self):
        """Should return None for regular text"""
        span_data = {"font": "regular", "size": 12, "flags": 0}

        result = detect_heading_level(span_data)

        assert result is None

    def test_detect_heading_level_bold_font_name(self):
        """Should detect heading with 'bold' in font name"""
        span_data = {"font": "Times-Bold", "size": 16, "flags": 0}

        result = detect_heading_level(span_data)

        assert result is not None


class TestDetectListItem:
    """Tests for detect_list_item function"""

    def test_detect_list_item_dash(self):
        """Should detect item starting with dash"""
        text = "- Item text"

        is_item, level = detect_list_item(text)

        assert is_item is True
        assert level == 1

    def test_detect_list_item_bullet(self):
        """Should detect item starting with bullet"""
        text = "• Item text"

        is_item, level = detect_list_item(text)

        assert is_item is True

    def test_detect_list_item_asterisk(self):
        """Should detect item starting with asterisk"""
        text = "* Item text"

        is_item, level = detect_list_item(text)

        assert is_item is True

    def test_detect_list_item_numbered(self):
        """Should detect numbered list item"""
        text = "1. First item"

        is_item, level = detect_list_item(text)

        assert is_item is True

    def test_detect_list_item_nested_dash(self):
        """Should detect nested list item with dash"""
        text = "  - Nested item"

        is_item, level = detect_list_item(text)

        assert is_item is True
        assert level == 2

    def test_detect_list_item_double_nested_dash(self):
        """Should detect double-nested list item"""
        text = "    - Double nested"

        is_item, level = detect_list_item(text)

        assert is_item is True
        assert level == 3

    def test_detect_list_item_numbered_nested(self):
        """Should detect nested numbered list"""
        text = "1.1. Nested numbered"

        is_item, level = detect_list_item(text)

        assert is_item is True

    def test_detect_list_item_not_list(self):
        """Should return False for non-list text"""
        text = "Regular paragraph text"

        is_item, level = detect_list_item(text)

        assert is_item is False
        assert level == 0

    def test_detect_list_item_dash_not_at_start(self):
        """Should not detect dash in middle of text"""
        text = "Text with - dash inside"

        is_item, level = detect_list_item(text)

        assert is_item is False

    def test_detect_list_item_empty_string(self):
        """Should handle empty string"""
        text = ""

        is_item, level = detect_list_item(text)

        assert is_item is False
        assert level == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
