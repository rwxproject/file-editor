#!/usr/bin/env python3
"""Basic usage examples for the file-editor library."""

import os
import tempfile

from file_editor import (
    AgentFileSystem,
    CSVEditor,
    MarkdownEditor,
    MmapEditor,
    StreamEditor,
    TextEditor,
)


def agent_filesystem_example():
    """Demonstrate agent-friendly file system usage."""
    print("=== Agent File System Example ===")

    # Create temporary workspace
    with tempfile.TemporaryDirectory() as temp_dir:
        # Initialize agent file system
        agent_fs = AgentFileSystem(temp_dir)

        # Create a file
        content = """# My Document

## Introduction
This is an example document.

## Features
- Feature 1
- Feature 2
- Feature 3

## Conclusion
This concludes our example.
"""
        agent_fs.create_file("document.md", content)
        print("Created document.md")

        # Read a specific section
        section = agent_fs.read_file_section("document.md", 3, 7)
        print(f"Section (lines 3-7):\n{section}\n")

        # Modify a section
        new_content = """## Features (Updated)
- Enhanced Feature 1
- New Feature 2
- Improved Feature 3
- Brand New Feature 4"""

        success = agent_fs.modify_file_section("document.md", 6, 10, new_content)
        print(f"Modified section: {success}")

        # Search in file
        results = agent_fs.search_in_file("document.md", "Feature")
        print(f"Found {len(results)} lines containing 'Feature':")
        for line_num, line_content in results[:3]:  # Show first 3
            print(f"  Line {line_num}: {line_content}")

        # Get file stats
        stats = agent_fs.get_file_stats("document.md")
        print(f"File stats: {stats}")


def memory_mapped_example():
    """Demonstrate memory-mapped file editing."""
    print("\n=== Memory-Mapped File Example ===")

    with tempfile.NamedTemporaryFile(mode="w+b", delete=False) as tmp:
        # Create test data
        test_data = b"Hello, World! This is a test for memory-mapped editing. " * 100
        tmp.write(test_data)
        tmp_path = tmp.name

    try:
        with MmapEditor(tmp_path) as editor:
            print(f"File size: {editor.size()} bytes")

            # Find and replace patterns
            positions = editor.find_all(b"World")
            print(f"Found 'World' at {len(positions)} positions")

            # Replace first occurrence
            pos = editor.replace(b"World", b"Earth")
            print(f"Replaced 'World' with 'Earth' at position {pos}")

            # Read a slice
            sample = editor.read_slice(0, 50)
            print(f"First 50 bytes: {sample}")

            editor.flush()

    finally:
        os.unlink(tmp_path)


def streaming_example():
    """Demonstrate streaming file processing."""
    print("\n=== Streaming File Example ===")

    with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp:
        # Create test file with many lines
        for i in range(1000):
            tmp.write(f"Line {i+1}: This is line number {i+1} in our test file.\n")
        tmp_path = tmp.name

    try:
        editor = StreamEditor(tmp_path)

        # Count lines efficiently
        line_count = editor.count_lines()
        print(f"Total lines: {line_count}")

        # Get first and last 5 lines
        first_lines = editor.head(5)
        last_lines = editor.tail(5)

        print("First 5 lines:")
        for line in first_lines:
            print(f"  {line}")

        print("Last 5 lines:")
        for line in last_lines:
            print(f"  {line}")

        # Process lines with transformation
        def uppercase_line(line: str) -> str:
            if "500" in line:
                return line.upper()
            return line

        output_path = editor.process_lines(uppercase_line)
        print(f"Processed file saved to: {output_path}")

        # Clean up processed file
        if output_path:
            os.unlink(output_path)

    finally:
        os.unlink(tmp_path)


def markdown_example():
    """Demonstrate markdown-specific editing."""
    print("\n=== Markdown Editor Example ===")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".md", delete=False) as tmp:
        markdown_content = """# Project Documentation

## Overview
This project provides file editing capabilities.

## Installation
Run pip install to install the package.

## Usage
Import the library and start editing files.

## API Reference
Detailed API documentation goes here.

## Examples
Code examples are provided below.
"""
        tmp.write(markdown_content)
        tmp_path = tmp.name

    try:
        editor = MarkdownEditor(tmp_path)

        # Get all sections
        sections = editor.get_sections()
        print(f"Found {len(sections)} sections:")
        for section in sections:
            print(f"  Level {section.level}: {section.title}")

        # Edit a specific section
        new_usage_content = """Here's how to use the library:

```python
from file_editor import AgentFileSystem

# Create file system
fs = AgentFileSystem("workspace")

# Edit files safely
fs.modify_file_section("file.txt", 1, 5, "new content")
```

The library provides multiple editing strategies for different use cases."""

        success = editor.edit_section_streaming("Usage", new_usage_content)
        print(f"Updated Usage section: {success}")

        # Insert a new section
        success = editor.insert_section(
            "Contributing",
            "Contributions are welcome! Please see CONTRIBUTING.md for guidelines.",
            level=2,
            after_section="Examples",
        )
        print(f"Inserted Contributing section: {success}")

        # Generate table of contents
        toc = editor.get_table_of_contents()
        print("Generated TOC:")
        print(toc)

    finally:
        os.unlink(tmp_path)


def csv_example():
    """Demonstrate CSV editing capabilities."""
    print("\n=== CSV Editor Example ===")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".csv", delete=False) as tmp:
        csv_content = """name,age,city,salary
John Doe,30,New York,75000
Jane Smith,25,Los Angeles,68000
Bob Johnson,35,Chicago,82000
Alice Brown,28,Houston,71000
Charlie Wilson,32,Phoenix,79000
"""
        tmp.write(csv_content)
        tmp_path = tmp.name

    try:
        editor = CSVEditor(tmp_path)

        # Get basic info
        headers = editor.get_headers()
        row_count = editor.count_rows()
        print(f"CSV has {len(headers)} columns and {row_count} rows")
        print(f"Headers: {headers}")

        # Get column statistics
        age_stats = editor.get_column_stats("age")
        salary_stats = editor.get_column_stats("salary")
        print(f"Age statistics: {age_stats}")
        print(f"Salary statistics: {salary_stats}")

        # Filter high earners
        output_path = editor.filter_rows(
            lambda row: int(row.get("salary", "0")) > 75000
        )

        if output_path:
            print(f"Filtered high earners to: {output_path}")

            # Read filtered results
            filtered_editor = CSVEditor(output_path)
            print(f"High earners: {filtered_editor.count_rows()} people")

            # Clean up
            os.unlink(output_path)

        # Add a new column
        output_path = editor.add_column(
            "tax_bracket",
            lambda row: "high" if int(row.get("salary", "0")) > 75000 else "standard",
        )

        if output_path:
            print(f"Added tax bracket column to: {output_path}")
            os.unlink(output_path)

    finally:
        os.unlink(tmp_path)


def text_editor_example():
    """Demonstrate text editing capabilities."""
    print("\n=== Text Editor Example ===")

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as tmp:
        python_code = """#!/usr/bin/env python3
def hello_world():
    print("Hello, World!")

def main():
    hello_world()
    print("This is a test file")
    print("With multiple lines")

if __name__ == "__main__":
    main()
"""
        tmp.write(python_code)
        tmp_path = tmp.name

    try:
        editor = TextEditor(tmp_path)

        # Get word count
        stats = editor.word_count()
        print(f"Text statistics: {stats}")

        # Find lines with specific patterns
        print("Lines containing 'print':")
        for line_num, line_content in editor.find_lines("print"):
            print(f"  Line {line_num}: {line_content.strip()}")

        # Comment out the main() call
        success = editor.comment_lines(6, 6, "# ")
        print(f"Commented out main() call: {success}")

        # Insert new lines
        new_lines = [
            "    # Added logging",
            "    import logging",
            "    logging.info('Application started')",
        ]
        success = editor.insert_lines(6, new_lines)
        print(f"Inserted logging code: {success}")

        # Replace a function name
        success = editor.replace_in_lines("hello_world", "greet_user")
        print(f"Renamed function: {success}")

    finally:
        os.unlink(tmp_path)


if __name__ == "__main__":
    agent_filesystem_example()
    memory_mapped_example()
    streaming_example()
    markdown_example()
    csv_example()
    text_editor_example()

    print("\n=== All examples completed successfully! ===")
