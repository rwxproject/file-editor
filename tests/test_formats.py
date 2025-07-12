"""Comprehensive tests for format-specific editors."""
import csv
import tempfile
from pathlib import Path
from typing import Any

import pytest
from file_editor.formats.csv import CSVEditor, PandasCSVEditor
from file_editor.formats.markdown import MarkdownEditor
from file_editor.formats.text import FastTextEditor, TextEditor
from hypothesis import given
from hypothesis import strategies as st


class TestMarkdownEditor:
    """Test markdown editor functionality."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.md"

    def teardown_method(self) -> None:
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_section_parsing(self) -> None:
        """Test parsing of markdown sections."""
        markdown_content = """# Main Title

Some introduction text.

## Section 1
Content for section 1.

### Subsection 1.1
Nested content.

## Section 2
Content for section 2.

### Subsection 2.1
More nested content.

#### Deep subsection
Very nested content.

## Section 3
Final section content.
"""

        self.test_file.write_text(markdown_content)
        editor = MarkdownEditor(self.test_file)

        sections = editor.get_sections()

        # Should find all sections
        assert len(sections) >= 6

        # Check specific sections
        section_titles = [s.title for s in sections]
        assert "Main Title" in section_titles
        assert "Section 1" in section_titles
        assert "Subsection 1.1" in section_titles
        assert "Section 2" in section_titles

        # Check section levels
        main_section = next(s for s in sections if s.title == "Main Title")
        assert main_section.level == 1

        sub_section = next(s for s in sections if s.title == "Subsection 1.1")
        assert sub_section.level == 3

    def test_find_section_by_title(self) -> None:
        """Test finding specific sections by title."""
        markdown_content = """# Document

## Introduction
Intro content.

## Features
Feature list.

## Conclusion
Final thoughts.
"""

        self.test_file.write_text(markdown_content)
        editor = MarkdownEditor(self.test_file)

        # Find existing section
        section = editor.find_section("Features")
        assert section is not None
        assert section.title == "Features"
        assert section.level == 2
        assert "Feature list" in section.content

        # Try to find non-existent section
        section = editor.find_section("Non-existent")
        assert section is None

    def test_find_sections_by_level(self) -> None:
        """Test finding sections by heading level."""
        markdown_content = """# Title

## Section A
Content A.

### Subsection A.1
Sub content A.1.

## Section B
Content B.

### Subsection B.1
Sub content B.1.

### Subsection B.2
Sub content B.2.
"""

        self.test_file.write_text(markdown_content)
        editor = MarkdownEditor(self.test_file)

        # Find level 2 sections
        level2_sections = editor.find_sections_by_level(2)
        assert len(level2_sections) == 2
        titles = [s.title for s in level2_sections]
        assert "Section A" in titles
        assert "Section B" in titles

        # Find level 3 sections
        level3_sections = editor.find_sections_by_level(3)
        assert len(level3_sections) == 3
        titles = [s.title for s in level3_sections]
        assert "Subsection A.1" in titles
        assert "Subsection B.1" in titles
        assert "Subsection B.2" in titles

    def test_edit_section_streaming(self) -> None:
        """Test streaming section editing."""
        markdown_content = """# Document Title

## Introduction
Old introduction content.

## Main Content
Important content here.

## Conclusion
Final remarks.
"""

        self.test_file.write_text(markdown_content)
        editor = MarkdownEditor(self.test_file)

        # Edit introduction section
        new_intro = """Welcome to our documentation!

This guide will help you understand our system.

Key points:
- Easy to use
- Well documented
- Fully tested"""

        success = editor.edit_section_streaming("Introduction", new_intro)
        assert success

        # Verify edit
        content = self.test_file.read_text()
        assert "Welcome to our documentation!" in content
        assert "Easy to use" in content
        assert "Important content here." in content  # Other sections preserved
        assert "Final remarks." in content

    def test_insert_section(self) -> None:
        """Test inserting new sections."""
        markdown_content = """# Project

## Overview
Project overview.

## Installation
Install instructions.

## Usage
Usage examples.
"""

        self.test_file.write_text(markdown_content)
        editor = MarkdownEditor(self.test_file)

        # Insert new section after Installation
        new_section_content = """First, ensure you have Python 3.8+:

```bash
python --version
```

Then install dependencies:

```bash
pip install -r requirements.txt
```"""

        success = editor.insert_section(
            "Prerequisites", new_section_content, level=2, after_section="Installation"
        )
        assert success

        # Verify insertion
        content = self.test_file.read_text()
        assert "## Prerequisites" in content
        assert "python --version" in content

        # Check order is correct
        lines = content.split("\n")
        install_idx = next(
            i for i, line in enumerate(lines) if "## Installation" in line
        )
        prereq_idx = next(
            i for i, line in enumerate(lines) if "## Prerequisites" in line
        )
        usage_idx = next(i for i, line in enumerate(lines) if "## Usage" in line)

        assert install_idx < prereq_idx < usage_idx

    def test_insert_section_at_end(self) -> None:
        """Test inserting section at end of document."""
        markdown_content = """# Document

## Section 1
Content 1.
"""

        self.test_file.write_text(markdown_content)
        editor = MarkdownEditor(self.test_file)

        success = editor.insert_section("New Section", "New content.", level=2)
        assert success

        content = self.test_file.read_text()
        assert "## New Section" in content
        assert "New content." in content

    def test_remove_section(self) -> None:
        """Test removing sections."""
        markdown_content = """# Document

## Keep This
Important content.

## Remove This
Content to be removed.

## Keep This Too
More important content.
"""

        self.test_file.write_text(markdown_content)
        editor = MarkdownEditor(self.test_file)

        success = editor.remove_section("Remove This")
        assert success

        content = self.test_file.read_text()
        assert "Remove This" not in content
        assert "Content to be removed" not in content
        assert "Keep This" in content
        assert "Keep This Too" in content

    def test_table_of_contents_generation(self) -> None:
        """Test TOC generation."""
        markdown_content = """# Main Document

## Introduction
Intro content.

### Background
Background info.

## Implementation
Implementation details.

### Architecture
System architecture.

### Database Design
Database schema.

## Conclusion
Final thoughts.
"""

        self.test_file.write_text(markdown_content)
        editor = MarkdownEditor(self.test_file)

        toc = editor.get_table_of_contents()

        # Check TOC structure
        assert "- [Main Document](#main-document)" in toc
        assert "- [Introduction](#introduction)" in toc
        assert "  - [Background](#background)" in toc
        assert "- [Implementation](#implementation)" in toc
        assert "    - [Architecture](#architecture)" in toc
        assert "    - [Database Design](#database-design)" in toc

    def test_update_links(self) -> None:
        """Test updating markdown links."""
        markdown_content = """# Document

Check out [our website](https://old-site.com) for more info.

Also see [documentation](https://old-docs.com/guide).

External link: [GitHub](https://github.com/example/repo)
"""

        self.test_file.write_text(markdown_content)
        editor = MarkdownEditor(self.test_file)

        # Update some links
        link_map = {
            "https://old-site.com": "https://new-site.com",
            "https://old-docs.com/guide": "https://docs.new-site.com/guide",
        }

        success = editor.update_links(link_map)
        assert success

        content = self.test_file.read_text()
        assert "https://new-site.com" in content
        assert "https://docs.new-site.com/guide" in content
        assert "https://old-site.com" not in content
        assert "https://github.com/example/repo" in content  # Unchanged

    def test_complex_markdown_structure(self) -> None:
        """Test handling of complex markdown with various elements."""
        complex_markdown = """# Project Documentation

![Logo](logo.png)

## Table of Contents
- [Overview](#overview)
- [Installation](#installation)

## Overview

This project does amazing things.

> **Note**: This is important!

### Key Features

1. Feature one
2. Feature two
   - Sub-feature A
   - Sub-feature B
3. Feature three

## Installation

```bash
npm install awesome-project
```

### Requirements

| Requirement | Version |
|-------------|---------|
| Node.js     | 14+     |
| npm         | 6+      |

## Usage

Here's how to use it:

```javascript
const awesome = require('awesome-project');
awesome.doSomething();
```

---

## API Reference

### Methods

#### `doSomething()`

Does something amazing.

**Parameters:**
- `param1` (string): Description
- `param2` (number): Another description

**Returns:** Promise<string>
"""

        self.test_file.write_text(complex_markdown)
        editor = MarkdownEditor(self.test_file)

        # Should be able to parse complex structure
        sections = editor.get_sections()
        assert len(sections) > 5

        # Should be able to edit sections with complex content
        new_overview = """This project revolutionizes everything!

It provides:
- Revolutionary feature A
- Groundbreaking feature B
- Mind-blowing feature C

Check the [demo](https://demo.example.com) to see it in action."""

        success = editor.edit_section_streaming("Overview", new_overview)
        assert success

        content = self.test_file.read_text()
        assert "revolutionizes everything" in content
        assert "demo.example.com" in content
        # Other complex elements should be preserved
        assert "```bash" in content
        assert "| Requirement" in content

    def test_empty_document_handling(self) -> None:
        """Test handling of empty or minimal documents."""
        # Empty document
        self.test_file.write_text("")
        editor = MarkdownEditor(self.test_file)

        sections = editor.get_sections()
        assert len(sections) == 0

        # Insert section in empty document
        success = editor.insert_section("First Section", "First content.", level=1)
        assert success

        content = self.test_file.read_text()
        assert "# First Section" in content

    @given(
        section_title=st.text(min_size=1, max_size=50).filter(lambda x: "\n" not in x),
        section_content=st.text(max_size=500),
        section_level=st.integers(min_value=1, max_value=6),
    )
    def test_property_based_section_operations(
        self, section_title: str, section_content: str, section_level: int
    ) -> None:
        """Property-based testing for section operations."""
        # Create initial document
        self.test_file.write_text("# Initial Document\n\nSome content.")
        editor = MarkdownEditor(self.test_file)

        # Insert section
        success = editor.insert_section(section_title, section_content, section_level)
        if success:  # Might fail for invalid titles
            content = self.test_file.read_text()

            # Should contain the section title
            expected_heading = "#" * section_level + " " + section_title
            assert expected_heading in content

            # Should contain the content
            if section_content.strip():
                assert section_content in content


class TestCSVEditor:
    """Test CSV editor functionality."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.csv"

    def teardown_method(self) -> None:
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_header_reading(self) -> None:
        """Test reading CSV headers."""
        csv_content = """name,age,city,salary
John Doe,30,New York,75000
Jane Smith,25,Los Angeles,68000
"""

        self.test_file.write_text(csv_content)
        editor = CSVEditor(self.test_file)

        headers = editor.get_headers()
        assert headers == ["name", "age", "city", "salary"]

    def test_row_reading_as_lists(self) -> None:
        """Test reading rows as lists."""
        csv_content = """name,age,city
John,30,NYC
Jane,25,LA
Bob,35,Chicago
"""

        self.test_file.write_text(csv_content)
        editor = CSVEditor(self.test_file)

        rows = list(editor.read_rows())
        assert len(rows) == 3
        assert rows[0] == ["John", "30", "NYC"]
        assert rows[1] == ["Jane", "25", "LA"]
        assert rows[2] == ["Bob", "35", "Chicago"]

    def test_row_reading_as_dicts(self) -> None:
        """Test reading rows as dictionaries."""
        csv_content = """name,age,city
John,30,NYC
Jane,25,LA
"""

        self.test_file.write_text(csv_content)
        editor = CSVEditor(self.test_file)

        rows = list(editor.read_dict_rows())
        assert len(rows) == 2
        assert rows[0] == {"name": "John", "age": "30", "city": "NYC"}
        assert rows[1] == {"name": "Jane", "age": "25", "city": "LA"}

    def test_row_counting(self) -> None:
        """Test counting CSV rows."""
        csv_content = """name,age
John,30
Jane,25
Bob,35
Alice,28
"""

        self.test_file.write_text(csv_content)
        editor = CSVEditor(self.test_file)

        count = editor.count_rows()
        assert count == 4

    def test_row_processing(self) -> None:
        """Test processing rows with transformations."""
        csv_content = """name,salary
John,50000
Jane,60000
Bob,55000
"""

        self.test_file.write_text(csv_content)
        editor = CSVEditor(self.test_file)

        # Give everyone a 10% raise
        def raise_processor(row: dict[str, str]) -> dict[str, str]:
            new_salary = int(row["salary"]) * 1.1
            row["salary"] = str(int(new_salary))
            return row

        output_path = editor.process_rows(raise_processor)
        assert output_path is not None

        # Verify results
        result_editor = CSVEditor(output_path)
        rows = list(result_editor.read_dict_rows())

        assert int(rows[0]["salary"]) == 55000  # 50000 * 1.1
        assert int(rows[1]["salary"]) == 66000  # 60000 * 1.1
        assert int(rows[2]["salary"]) == 60500  # 55000 * 1.1

    def test_row_filtering(self) -> None:
        """Test filtering rows."""
        csv_content = """name,age,department
John,30,Engineering
Jane,25,Marketing
Bob,35,Engineering
Alice,28,Sales
"""

        self.test_file.write_text(csv_content)
        editor = CSVEditor(self.test_file)

        # Filter engineers
        output_path = editor.filter_rows(lambda row: row["department"] == "Engineering")
        assert output_path is not None

        # Verify results
        result_editor = CSVEditor(output_path)
        rows = list(result_editor.read_dict_rows())

        assert len(rows) == 2
        assert rows[0]["name"] == "John"
        assert rows[1]["name"] == "Bob"

    def test_column_updating(self) -> None:
        """Test updating column values."""
        csv_content = """name,status
John,active
Jane,inactive
Bob,active
"""

        self.test_file.write_text(csv_content)
        editor = CSVEditor(self.test_file)

        # Update status to uppercase
        output_path = editor.update_column("status", lambda x: x.upper())
        assert output_path is not None

        # Verify results
        result_editor = CSVEditor(output_path)
        rows = list(result_editor.read_dict_rows())

        assert rows[0]["status"] == "ACTIVE"
        assert rows[1]["status"] == "INACTIVE"
        assert rows[2]["status"] == "ACTIVE"

    def test_column_addition(self) -> None:
        """Test adding new columns."""
        csv_content = """name,salary
John,50000
Jane,60000
"""

        self.test_file.write_text(csv_content)
        editor = CSVEditor(self.test_file)

        # Add tax bracket column
        def tax_bracket(row: dict[str, str]) -> str:
            salary = int(row["salary"])
            return "high" if salary > 55000 else "standard"

        output_path = editor.add_column("tax_bracket", tax_bracket)
        assert output_path is not None

        # Verify results
        result_editor = CSVEditor(output_path)
        headers = result_editor.get_headers()
        assert "tax_bracket" in headers

        rows = list(result_editor.read_dict_rows())
        assert rows[0]["tax_bracket"] == "standard"  # 50000
        assert rows[1]["tax_bracket"] == "high"  # 60000

    def test_column_statistics(self) -> None:
        """Test column statistics calculation."""
        csv_content = """name,age,salary,department
John,30,75000,Engineering
Jane,25,68000,Marketing
Bob,35,,Engineering
Alice,28,71000,
Charlie,,82000,Engineering
"""

        self.test_file.write_text(csv_content)
        editor = CSVEditor(self.test_file)

        # Test age statistics
        age_stats = editor.get_column_stats("age")
        assert age_stats["total_rows"] == 5
        assert age_stats["non_empty_rows"] == 4
        assert age_stats["empty_rows"] == 1
        assert age_stats["unique_values"] == 4
        assert age_stats["numeric_count"] == 4
        assert age_stats["min_value"] == 25.0
        assert age_stats["max_value"] == 35.0
        assert age_stats["avg_value"] == 29.5

        # Test salary statistics
        salary_stats = editor.get_column_stats("salary")
        assert salary_stats["total_rows"] == 5
        assert salary_stats["non_empty_rows"] == 4
        assert salary_stats["numeric_count"] == 4

    def test_sorting(self) -> None:
        """Test CSV sorting functionality."""
        csv_content = """name,age,salary
John,30,75000
Jane,25,68000
Bob,35,82000
Alice,28,71000
"""

        self.test_file.write_text(csv_content)
        editor = CSVEditor(self.test_file)

        # Sort by age
        success = editor.sort_by_column("age")
        assert success

        # Verify sorting
        rows = list(editor.read_dict_rows())
        ages = [int(row["age"]) for row in rows]
        assert ages == [25, 28, 30, 35]  # Sorted ascending

        # Sort by salary descending
        success = editor.sort_by_column("salary", reverse=True, key_func=int)
        assert success

        rows = list(editor.read_dict_rows())
        salaries = [int(row["salary"]) for row in rows]
        assert salaries[0] > salaries[1] > salaries[2] > salaries[3]

    def test_custom_delimiter(self) -> None:
        """Test CSV with custom delimiter."""
        tsv_content = """name\tage\tcity
John\t30\tNYC
Jane\t25\tLA
"""

        self.test_file.write_text(tsv_content)
        editor = CSVEditor(self.test_file, delimiter="\t")

        headers = editor.get_headers()
        assert headers == ["name", "age", "city"]

        rows = list(editor.read_dict_rows())
        assert rows[0]["name"] == "John"
        assert rows[0]["age"] == "30"

    def test_quoted_fields(self) -> None:
        """Test CSV with quoted fields."""
        csv_content = '''name,description,price
"John Doe","Software ""Engineer""",75000
"Jane Smith","Product Manager, Senior",85000
'''

        self.test_file.write_text(csv_content)
        editor = CSVEditor(self.test_file)

        rows = list(editor.read_dict_rows())
        assert rows[0]["name"] == "John Doe"
        assert rows[0]["description"] == 'Software "Engineer"'
        assert rows[1]["description"] == "Product Manager, Senior"

    def test_empty_csv_handling(self) -> None:
        """Test handling of empty CSV files."""
        # Empty file
        self.test_file.write_text("")
        editor = CSVEditor(self.test_file)

        headers = editor.get_headers()
        assert headers == []

        count = editor.count_rows()
        assert count == 0

        # Header only
        self.test_file.write_text("name,age,city\n")
        editor = CSVEditor(self.test_file)

        headers = editor.get_headers()
        assert headers == ["name", "age", "city"]

        count = editor.count_rows()
        assert count == 0

    @pytest.mark.performance
    def test_large_csv_processing(self, benchmark: Any) -> None:
        """Test performance with large CSV files."""
        # Create large CSV
        headers = ["id", "name", "value", "category"]

        with open(self.test_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(headers)

            for i in range(10000):
                writer.writerow([str(i), f"Name_{i}", str(i * 10), f"Category_{i % 5}"])

        def process_large_csv() -> int:
            editor = CSVEditor(self.test_file)
            count = 0
            for row in editor.read_dict_rows():
                if int(row["value"]) > 50000:
                    count += 1
            return count

        result = benchmark(process_large_csv)
        assert result > 4000  # Should find many rows with value > 50000


@pytest.mark.skipif(
    not hasattr(CSVEditor, "__module__") or "pandas" not in str(CSVEditor.__module__),
    reason="Pandas not available",
)
class TestPandasCSVEditor:
    """Test pandas-based CSV editor if available."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.csv"

    def teardown_method(self) -> None:
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_chunk_processing(self) -> None:
        """Test processing CSV in pandas chunks."""
        # Create larger CSV for chunking
        with open(self.test_file, "w", newline="") as f:
            writer = csv.writer(f)
            writer.writerow(["id", "value"])

            for i in range(1000):
                writer.writerow([str(i), str(i * 2)])

        try:
            editor = PandasCSVEditor(self.test_file, chunk_size=100)

            def double_values(chunk: Any) -> Any:
                chunk["value"] = chunk["value"] * 2
                return chunk

            output_path = editor.process_chunks(double_values)
            assert output_path is not None

            # Verify results
            result_editor = CSVEditor(output_path)
            first_row = next(result_editor.read_dict_rows())
            assert int(first_row["value"]) == 0  # 0 * 2 * 2 = 0

        except ImportError:
            pytest.skip("Pandas not available")


class TestTextEditor:
    """Test text editor functionality."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.txt"

    def teardown_method(self) -> None:
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_line_finding(self) -> None:
        """Test finding lines with patterns."""
        content = """def function_one():
    return "hello"

def function_two():
    return "world"

class MyClass:
    def method(self):
        pass
"""

        self.test_file.write_text(content)
        editor = TextEditor(self.test_file)

        # Find function definitions
        matches = list(editor.find_lines(r"def \w+"))
        assert len(matches) == 3

        line_numbers = [m[0] for m in matches]
        assert 1 in line_numbers  # function_one
        assert 4 in line_numbers  # function_two
        assert 8 in line_numbers  # method

    def test_find_and_replace(self) -> None:
        """Test find and replace operations."""
        content = """Hello world
This is a test
Hello universe
Another line
Hello galaxy
"""

        self.test_file.write_text(content)
        editor = TextEditor(self.test_file)

        # Replace all "Hello" with "Hi"
        success = editor.replace_in_lines("Hello", "Hi")
        assert success

        # Verify replacement
        result = self.test_file.read_text()
        assert "Hi world" in result
        assert "Hi universe" in result
        assert "Hi galaxy" in result
        assert "Hello" not in result

    def test_line_insertion(self) -> None:
        """Test inserting lines."""
        content = """Line 1
Line 2
Line 3
Line 4
"""

        self.test_file.write_text(content)
        editor = TextEditor(self.test_file)

        # Insert lines after line 2
        success = editor.insert_lines(3, ["Inserted Line A", "Inserted Line B"])
        assert success

        # Verify insertion
        result = self.test_file.read_text()
        lines = result.strip().split("\n")
        assert "Line 1" in lines[0]
        assert "Line 2" in lines[1]
        assert "Inserted Line A" in lines[2]
        assert "Inserted Line B" in lines[3]
        assert "Line 3" in lines[4]

    def test_line_deletion(self) -> None:
        """Test deleting lines."""
        content = """Line 1
Line 2
Line 3
Line 4
Line 5
"""

        self.test_file.write_text(content)
        editor = TextEditor(self.test_file)

        # Delete lines 2-4
        success = editor.delete_lines(2, 4)
        assert success

        # Verify deletion
        result = self.test_file.read_text()
        lines = result.strip().split("\n")
        assert len(lines) == 2
        assert "Line 1" in lines[0]
        assert "Line 5" in lines[1]

    def test_line_replacement(self) -> None:
        """Test replacing lines."""
        content = """Keep this
Replace this
Replace this too
Keep this too
"""

        self.test_file.write_text(content)
        editor = TextEditor(self.test_file)

        # Replace lines 2-3
        success = editor.replace_lines(2, 3, ["New line 1", "New line 2"])
        assert success

        # Verify replacement
        result = self.test_file.read_text()
        lines = result.strip().split("\n")
        assert "Keep this" in lines[0]
        assert "New line 1" in lines[1]
        assert "New line 2" in lines[2]
        assert "Keep this too" in lines[3]

    def test_commenting_and_uncommenting(self) -> None:
        """Test commenting and uncommenting lines."""
        content = """def function():
    print("Hello")
    return True
"""

        self.test_file.write_text(content)
        editor = TextEditor(self.test_file)

        # Comment out lines 2-3
        success = editor.comment_lines(2, 3, "# ")
        assert success

        result = self.test_file.read_text()
        assert '# print("Hello")' in result
        assert "# return True" in result

        # Uncomment lines
        success = editor.uncomment_lines(2, 3, "# ")
        assert success

        result = self.test_file.read_text()
        assert 'print("Hello")' in result
        assert "return True" in result
        assert "# print" not in result

    def test_indentation_operations(self) -> None:
        """Test indenting and dedenting lines."""
        content = """def function():
print("not indented")
return True
"""

        self.test_file.write_text(content)
        editor = TextEditor(self.test_file)

        # Indent lines 2-3
        success = editor.indent_lines(2, 3, "    ")
        assert success

        result = self.test_file.read_text()
        assert '    print("not indented")' in result
        assert "    return True" in result

        # Dedent lines
        success = editor.dedent_lines(2, 3, 4)
        assert success

        result = self.test_file.read_text()
        assert 'print("not indented")' in result
        assert "return True" in result

    def test_section_extraction(self) -> None:
        """Test extracting sections between patterns."""
        content = """# Configuration
config_start = True

database_host = "localhost"
database_port = 5432
database_name = "myapp"

config_end = True

# Main code
def main():
    pass
"""

        self.test_file.write_text(content)
        editor = TextEditor(self.test_file)

        # Extract configuration section
        section = editor.extract_section(
            r"config_start = True", r"config_end = True", include_markers=True
        )

        assert len(section) == 6  # Including markers and content
        assert "config_start = True" in section
        assert "database_host" in "\n".join(section)
        assert "config_end = True" in section

    def test_word_count(self) -> None:
        """Test word count functionality."""
        content = """Hello world
This is a test file
With multiple lines and words
"""

        self.test_file.write_text(content)
        editor = TextEditor(self.test_file)

        stats = editor.word_count()
        assert stats["lines"] == 3
        assert stats["words"] == 10
        assert stats["characters"] > 0

    def test_regex_operations(self) -> None:
        """Test regex-based operations."""
        content = """import os
import sys
from pathlib import Path
import numpy as np
"""

        self.test_file.write_text(content)
        editor = TextEditor(self.test_file)

        # Find import statements
        imports = list(editor.find_lines(r"^import \w+"))
        assert len(imports) == 3

        # Find from imports
        from_imports = list(editor.find_lines(r"^from \w+"))
        assert len(from_imports) == 1


class TestFastTextEditor:
    """Test fast text editor with line indexing."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.txt"

    def teardown_method(self) -> None:
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_indexed_line_access(self) -> None:
        """Test O(1) line access through indexing."""
        lines = [f"Line {i:04d}" for i in range(1000)]
        content = "\n".join(lines)
        self.test_file.write_text(content)

        editor = FastTextEditor(self.test_file)

        # Access specific lines
        assert editor.get_line(1) == "Line 0000"
        assert editor.get_line(500) == "Line 0499"
        assert editor.get_line(1000) == "Line 0999"

    def test_line_range_access(self) -> None:
        """Test accessing ranges of lines."""
        lines = [f"Line {i}" for i in range(100)]
        content = "\n".join(lines)
        self.test_file.write_text(content)

        editor = FastTextEditor(self.test_file)

        # Get range of lines
        range_lines = editor.get_lines_range(10, 15)
        assert len(range_lines) == 6  # 10-15 inclusive
        assert "Line 9" in range_lines[0]
        assert "Line 14" in range_lines[5]

    def test_fast_line_replacement(self) -> None:
        """Test fast single line replacement."""
        lines = [f"Line {i}" for i in range(10)]
        content = "\n".join(lines)
        self.test_file.write_text(content)

        editor = FastTextEditor(self.test_file)

        # Replace line 5
        success = editor.replace_line_fast(5, "Modified Line 4")
        assert success

        # Verify replacement
        new_content = self.test_file.read_text()
        assert "Modified Line 4" in new_content
        assert "Line 4" not in new_content

    @pytest.mark.performance
    def test_random_line_access_performance(self, benchmark: Any) -> None:
        """Benchmark random line access performance."""
        # Create large file
        lines = [f"Line {i:06d} with some content" for i in range(10000)]
        content = "\n".join(lines)
        self.test_file.write_text(content)

        editor = FastTextEditor(self.test_file)

        def random_access() -> int:
            total_chars = 0
            import random

            for _ in range(100):
                line_num = random.randint(1, 10000)
                line = editor.get_line(line_num)
                total_chars += len(line)
            return total_chars

        result = benchmark(random_access)
        assert result > 2000  # Should access significant content
