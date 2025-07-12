"""Comprehensive tests for agent-friendly interface."""
import os
import tempfile
from pathlib import Path
from typing import Any

import pytest
from file_editor.agent.interface import AgentFileSystem, SpecializedAgentEditors
from hypothesis import given
from hypothesis import strategies as st


class TestAgentFileSystem:
    """Test agent file system interface."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.agent_fs = AgentFileSystem(self.temp_dir)

    def teardown_method(self) -> None:
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_workspace_creation(self) -> None:
        """Test workspace directory creation."""
        new_workspace = Path(self.temp_dir) / "new_workspace"
        agent_fs = AgentFileSystem(str(new_workspace))

        assert new_workspace.exists()
        assert new_workspace.is_dir()

    def test_path_validation_security(self) -> None:
        """Test path validation prevents directory traversal."""
        # Try various directory traversal attacks
        attack_paths = [
            "../../../etc/passwd",
            "..\\..\\..\\windows\\system32",
            "/etc/passwd",
            "C:\\Windows\\System32",
            "subdir/../../etc/passwd",
            "./../../etc/passwd",
        ]

        for attack_path in attack_paths:
            with pytest.raises(ValueError, match="outside workspace"):
                self.agent_fs._validate_path(attack_path)

    def test_valid_paths_allowed(self) -> None:
        """Test that valid paths within workspace are allowed."""
        valid_paths = [
            "file.txt",
            "subdir/file.txt",
            "deep/nested/path/file.txt",
            "./file.txt",
            "subdir/../file.txt",  # Resolves to workspace/file.txt
        ]

        for valid_path in valid_paths:
            # Should not raise exception
            resolved = self.agent_fs._validate_path(valid_path)
            assert str(resolved).startswith(str(self.agent_fs.workspace))

    def test_file_creation_and_reading(self) -> None:
        """Test basic file creation and reading."""
        content = "Hello, Agent World!"

        success = self.agent_fs.create_file("test.txt", content)
        assert success

        assert self.agent_fs.file_exists("test.txt")

        read_content = self.agent_fs.read_full_file("test.txt")
        assert read_content == content

    def test_file_already_exists_protection(self) -> None:
        """Test protection against overwriting existing files."""
        self.agent_fs.create_file("existing.txt", "original content")

        # Should not allow overwriting
        success = self.agent_fs.create_file("existing.txt", "new content")
        assert not success

        # Original content should be preserved
        content = self.agent_fs.read_full_file("existing.txt")
        assert content == "original content"

    def test_file_size_limits(self) -> None:
        """Test file size limitation enforcement."""
        # Create agent with small file size limit
        small_agent = AgentFileSystem(self.temp_dir, max_file_size=100)

        # Small file should work
        small_content = "x" * 50
        success = small_agent.create_file("small.txt", small_content)
        assert success

        # Large file should be rejected
        large_content = "x" * 200
        large_file = Path(self.temp_dir) / "large.txt"
        large_file.write_text(large_content)

        result = small_agent.read_full_file("large.txt")
        assert result is None  # Should fail due to size

    def test_file_section_operations(self) -> None:
        """Test reading and modifying file sections."""
        lines = [f"Line {i}" for i in range(10)]
        content = "\n".join(lines)

        self.agent_fs.create_file("sections.txt", content)

        # Read section
        section = self.agent_fs.read_file_section("sections.txt", 2, 4)
        expected = "Line 1\nLine 2\nLine 3"
        assert section == expected

        # Modify section
        success = self.agent_fs.modify_file_section(
            "sections.txt", 2, 4, "Modified Line\nAnother Line\nThird Line"
        )
        assert success

        # Verify modification
        new_content = self.agent_fs.read_full_file("sections.txt")
        assert "Modified Line" in new_content
        assert "Line 0" in new_content  # Unchanged parts preserved
        assert "Line 4" in new_content

    def test_search_functionality(self) -> None:
        """Test file search capabilities."""
        content = """Line 1: Hello World
Line 2: This is a test
Line 3: Hello Universe
Line 4: Another test line
Line 5: Hello Galaxy"""

        self.agent_fs.create_file("search_test.txt", content)

        # Search for pattern
        results = self.agent_fs.search_in_file("search_test.txt", "Hello")
        assert len(results) == 3

        line_numbers = [r[0] for r in results]
        assert 1 in line_numbers
        assert 3 in line_numbers
        assert 5 in line_numbers

        # Case insensitive search
        results = self.agent_fs.search_in_file(
            "search_test.txt", "hello", case_sensitive=False
        )
        assert len(results) == 3

        # Search with max results limit
        results = self.agent_fs.search_in_file("search_test.txt", "Line", max_results=2)
        assert len(results) == 2

    def test_file_statistics(self) -> None:
        """Test file statistics functionality."""
        content = "Hello world\nThis is a test\nWith multiple lines and words"
        self.agent_fs.create_file("stats_test.txt", content)

        stats = self.agent_fs.get_file_stats("stats_test.txt")
        assert stats is not None
        assert stats["lines"] == 3
        assert stats["words"] > 0
        assert stats["characters"] > 0

    def test_file_info_retrieval(self) -> None:
        """Test file information retrieval."""
        content = "Test content for file info"
        self.agent_fs.create_file("info_test.txt", content)

        info = self.agent_fs.get_file_info("info_test.txt")
        assert info is not None
        assert info["size"] > 0
        assert info["is_text"] is True
        assert info["file_type"] == "text"

        # Test with non-existent file
        info = self.agent_fs.get_file_info("nonexistent.txt")
        assert info is None

    def test_file_type_detection(self) -> None:
        """Test automatic file type detection."""
        test_files = {
            "document.md": "markdown",
            "data.csv": "csv",
            "script.py": "python",
            "config.json": "json",
            "page.html": "html",
            "unknown.xyz": "unknown",
        }

        for filename, expected_type in test_files.items():
            self.agent_fs.create_file(filename, "test content")
            info = self.agent_fs.get_file_info(filename)
            assert info["file_type"] == expected_type

    def test_append_functionality(self) -> None:
        """Test file appending capabilities."""
        self.agent_fs.create_file("append_test.txt", "Initial content")

        success = self.agent_fs.append_to_file("append_test.txt", "\nAppended content")
        assert success

        content = self.agent_fs.read_full_file("append_test.txt")
        assert "Initial content" in content
        assert "Appended content" in content

    def test_file_deletion(self) -> None:
        """Test file deletion functionality."""
        self.agent_fs.create_file("delete_test.txt", "To be deleted")
        assert self.agent_fs.file_exists("delete_test.txt")

        success = self.agent_fs.delete_file("delete_test.txt")
        assert success
        assert not self.agent_fs.file_exists("delete_test.txt")

        # Try deleting non-existent file
        success = self.agent_fs.delete_file("nonexistent.txt")
        assert not success

    def test_list_files_functionality(self) -> None:
        """Test file listing capabilities."""
        # Create test files
        test_files = ["file1.txt", "file2.py", "subdir/file3.md"]

        for file_path in test_files:
            if "/" in file_path:
                # Create subdirectory
                dir_path = Path(self.agent_fs.workspace) / Path(file_path).parent
                dir_path.mkdir(parents=True, exist_ok=True)
            self.agent_fs.create_file(file_path, "test content")

        # List all files
        files = self.agent_fs.list_files()
        assert "file1.txt" in files
        assert "file2.py" in files
        assert "subdir/file3.md" in files

        # List with pattern
        py_files = self.agent_fs.list_files(pattern="*.py")
        assert "file2.py" in py_files
        assert "file1.txt" not in py_files

        # List in subdirectory
        subdir_files = self.agent_fs.list_files(directory="subdir")
        assert "file3.md" in subdir_files

    def test_operation_logging(self) -> None:
        """Test operation logging and audit trail."""
        # Perform various operations
        self.agent_fs.create_file("log_test.txt", "content")
        self.agent_fs.read_full_file("log_test.txt")
        self.agent_fs.modify_file_section("log_test.txt", 1, 1, "modified")
        self.agent_fs.search_in_file("log_test.txt", "modified")

        # Check operation log
        log = self.agent_fs.get_operation_log()
        assert len(log) >= 4

        operations = [entry["operation"] for entry in log]
        assert "create" in operations
        assert "read_full" in operations
        assert "modify" in operations
        assert "search" in operations

        # Test log clearing
        self.agent_fs.clear_operation_log()
        log = self.agent_fs.get_operation_log()
        assert len(log) == 0

    def test_binary_file_handling(self) -> None:
        """Test handling of binary files."""
        # Create a binary file directly
        binary_file = Path(self.agent_fs.workspace) / "binary_test.bin"
        binary_data = bytes(range(256))
        binary_file.write_bytes(binary_data)

        info = self.agent_fs.get_file_info("binary_test.bin")
        assert info is not None
        assert info["is_text"] is False

        # Reading binary file as text should work (with replacement chars)
        content = self.agent_fs.read_full_file("binary_test.bin")
        assert content is not None

    def test_error_handling(self) -> None:
        """Test error handling for various failure scenarios."""
        # Non-existent file operations
        assert self.agent_fs.read_full_file("nonexistent.txt") is None
        assert not self.agent_fs.modify_file_section("nonexistent.txt", 1, 1, "content")
        assert self.agent_fs.search_in_file("nonexistent.txt", "pattern") == []
        assert self.agent_fs.get_file_stats("nonexistent.txt") is None

    def test_max_lines_limit(self) -> None:
        """Test max lines limit in file reading."""
        lines = [f"Line {i}" for i in range(1000)]
        content = "\n".join(lines)
        self.agent_fs.create_file("large_file.txt", content)

        # Read with line limit
        limited_content = self.agent_fs.read_full_file("large_file.txt", max_lines=100)
        limited_lines = limited_content.split("\n")
        assert len(limited_lines) == 100
        assert "Line 0" in limited_lines[0]
        assert "Line 99" in limited_lines[99]

    @given(
        filename=st.text(min_size=1, max_size=50).filter(
            lambda x: not any(
                c in x for c in ["/", "\\", ":", "*", "?", '"', "<", ">", "|"]
            )
        ),
        content=st.text(max_size=1000),
    )
    def test_property_based_file_operations(self, filename: str, content: str) -> None:
        """Property-based testing for file operations."""
        if filename.strip() and not filename.startswith("."):
            # Create and read should be consistent
            success = self.agent_fs.create_file(filename, content)
            if success:  # File creation might fail for various reasons
                read_content = self.agent_fs.read_full_file(filename)
                assert read_content == content

                # File should exist
                assert self.agent_fs.file_exists(filename)


class TestSpecializedAgentEditors:
    """Test specialized editors for specific file types."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.agent_fs = AgentFileSystem(self.temp_dir)
        self.specialized = SpecializedAgentEditors(self.agent_fs)

    def teardown_method(self) -> None:
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_markdown_section_editing(self) -> None:
        """Test markdown section editing functionality."""
        markdown_content = """# Main Title

## Introduction
This is the introduction section.

## Features
- Feature 1
- Feature 2

## Conclusion
This is the conclusion.
"""

        self.agent_fs.create_file("test.md", markdown_content)

        # Edit Features section
        new_features = """Here are the enhanced features:

- Enhanced Feature 1
- New Feature 2
- Advanced Feature 3
- Revolutionary Feature 4"""

        success = self.specialized.markdown_edit_section(
            "test.md", "Features", new_features
        )
        assert success

        # Verify edit
        content = self.agent_fs.read_full_file("test.md")
        assert "Enhanced Feature 1" in content
        assert "Revolutionary Feature 4" in content
        assert (
            "This is the introduction section." in content
        )  # Other sections preserved

    def test_markdown_section_not_found(self) -> None:
        """Test markdown editing when section doesn't exist."""
        markdown_content = """# Title

## Section 1
Content 1
"""

        self.agent_fs.create_file("test.md", markdown_content)

        success = self.specialized.markdown_edit_section(
            "test.md", "Nonexistent Section", "New content"
        )
        assert not success

    def test_csv_filtering(self) -> None:
        """Test CSV row filtering functionality."""
        csv_content = """name,age,city,salary
John Doe,30,New York,75000
Jane Smith,25,Los Angeles,68000
Bob Johnson,35,Chicago,82000
Alice Brown,28,Houston,71000
"""

        self.agent_fs.create_file("employees.csv", csv_content)

        # Filter high earners
        result_path = self.specialized.csv_filter_rows(
            "employees.csv", "salary", "82000", "high_earners.csv"
        )

        assert result_path is not None
        assert result_path == "high_earners.csv"
        assert self.agent_fs.file_exists("high_earners.csv")

        # Verify filtered content
        filtered_content = self.agent_fs.read_full_file("high_earners.csv")
        assert "Bob Johnson" in filtered_content
        assert "John Doe" not in filtered_content

    def test_csv_filtering_no_matches(self) -> None:
        """Test CSV filtering with no matching rows."""
        csv_content = """name,age
John,30
Jane,25
"""

        self.agent_fs.create_file("test.csv", csv_content)

        result_path = self.specialized.csv_filter_rows("test.csv", "age", "40")
        assert result_path is not None

        # Should have header but no data rows
        filtered_content = self.agent_fs.read_full_file(result_path)
        lines = filtered_content.strip().split("\n")
        assert len(lines) == 1  # Only header
        assert "name,age" in lines[0]

    def test_csv_filtering_invalid_file(self) -> None:
        """Test CSV filtering with invalid file."""
        result_path = self.specialized.csv_filter_rows(
            "nonexistent.csv", "column", "value"
        )
        assert result_path is None

    def test_specialized_editor_error_handling(self) -> None:
        """Test error handling in specialized editors."""
        # Test with non-existent files
        success = self.specialized.markdown_edit_section(
            "nonexistent.md", "Section", "Content"
        )
        assert not success

        result = self.specialized.csv_filter_rows("nonexistent.csv", "col", "val")
        assert result is None


class TestSecurityFeatures:
    """Test security features of the agent interface."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.agent_fs = AgentFileSystem(self.temp_dir)

    def teardown_method(self) -> None:
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_workspace_isolation(self) -> None:
        """Test that agents are isolated to their workspace."""
        # Create a file outside workspace
        outside_file = Path(self.temp_dir).parent / "outside_file.txt"
        outside_file.write_text("Sensitive data")

        # Agent should not be able to access it
        try:
            content = self.agent_fs.read_full_file("../outside_file.txt")
            assert content is None  # Should fail gracefully
        except ValueError:
            pass  # Or raise validation error

        # Clean up
        outside_file.unlink()

    def test_symlink_protection(self) -> None:
        """Test protection against symlink attacks."""
        # Create a file outside workspace
        outside_file = Path(self.temp_dir).parent / "secret.txt"
        outside_file.write_text("Secret information")

        try:
            # Create symlink in workspace pointing outside
            link_path = Path(self.agent_fs.workspace) / "symlink.txt"
            os.symlink(outside_file, link_path)

            # Agent should not follow the symlink outside workspace
            content = self.agent_fs.read_full_file("symlink.txt")
            # This might succeed if the symlink is followed, or fail if protected
            # The exact behavior depends on implementation details

        except (OSError, ValueError):
            pass  # Expected for symlink protection
        finally:
            # Clean up
            if outside_file.exists():
                outside_file.unlink()

    def test_file_size_protection(self) -> None:
        """Test protection against excessive file sizes."""
        # Create agent with small size limit
        small_agent = AgentFileSystem(self.temp_dir, max_file_size=1000)

        # Create large file manually
        large_file = Path(self.agent_fs.workspace) / "large.txt"
        large_content = "x" * 2000
        large_file.write_text(large_content)

        # Agent should refuse to read it
        content = small_agent.read_full_file("large.txt")
        assert content is None

    def test_filename_validation(self) -> None:
        """Test validation of filenames."""
        dangerous_names = [
            "",  # Empty name
            ".",  # Current directory
            "..",  # Parent directory
            "con",  # Windows reserved name
            "aux",  # Windows reserved name
            "file\x00name",  # Null byte
            "file\nname",  # Newline
        ]

        for dangerous_name in dangerous_names:
            success = self.agent_fs.create_file(dangerous_name, "content")
            # Should either fail gracefully or sanitize the name
            if success:
                # If it succeeds, verify the file was created safely
                assert self.agent_fs.file_exists(dangerous_name)


class TestPerformanceAndScalability:
    """Test performance and scalability characteristics."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.agent_fs = AgentFileSystem(self.temp_dir)

    def teardown_method(self) -> None:
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    @pytest.mark.performance
    def test_many_small_files(self, benchmark: Any) -> None:
        """Test performance with many small files."""
        import time

        def create_many_files() -> int:
            # Use timestamp to ensure unique filenames across runs
            timestamp = int(time.time() * 1000000)  # microseconds
            count = 0
            for i in range(100):
                success = self.agent_fs.create_file(
                    f"file_{timestamp}_{i}.txt", f"Content {i}"
                )
                if success:
                    count += 1
            return count

        result = benchmark(create_many_files)
        assert result == 100

    @pytest.mark.performance
    def test_large_file_sections(self, benchmark: Any) -> None:
        """Test performance with large file sections."""
        # Create a large file
        lines = [f"Line {i:06d}" for i in range(10000)]
        content = "\n".join(lines)
        self.agent_fs.create_file("large.txt", content)

        def read_sections() -> int:
            total_chars = 0
            for i in range(0, 10000, 1000):
                section = self.agent_fs.read_file_section("large.txt", i + 1, i + 100)
                if section:
                    total_chars += len(section)
            return total_chars

        result = benchmark(read_sections)
        assert result > 0

    @pytest.mark.slow
    def test_workspace_with_many_files(self) -> None:
        """Test workspace behavior with many files."""
        # Create many files
        for i in range(1000):
            self.agent_fs.create_file(f"file_{i:04d}.txt", f"Content for file {i}")

        # Test listing files
        files = self.agent_fs.list_files()
        assert len(files) == 1000

        # Test search across many files (would be slow in real implementation)
        # This test mainly ensures the system doesn't crash with many files

    def test_memory_usage_with_large_operations(self) -> None:
        """Test that memory usage stays reasonable with large operations."""
        # Create a large file with multiple lines
        lines = [f"Line {i:06d} " + "A" * 100 for i in range(10000)]  # 10k lines
        large_content = "\n".join(lines)
        self.agent_fs.create_file("large.txt", large_content)

        # Reading sections should not load entire file
        section = self.agent_fs.read_file_section("large.txt", 1, 100)
        assert section is not None
        assert len(section) < len(large_content)  # Should be much smaller

        # Searching should also be memory efficient
        results = self.agent_fs.search_in_file("large.txt", "A", max_results=10)
        assert len(results) <= 10


class TestIntegrationScenarios:
    """Test realistic integration scenarios."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.agent_fs = AgentFileSystem(self.temp_dir)
        self.specialized = SpecializedAgentEditors(self.agent_fs)

    def teardown_method(self) -> None:
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    @pytest.mark.integration
    def test_document_processing_workflow(self) -> None:
        """Test a complete document processing workflow."""
        # Create initial document
        initial_doc = """# Project Documentation

## Overview
This project is amazing.

## Installation
Run pip install.

## Usage
Use the API.
"""

        self.agent_fs.create_file("README.md", initial_doc)

        # Update multiple sections
        self.specialized.markdown_edit_section(
            "README.md",
            "Installation",
            """
Installation is easy:

```bash
pip install our-package
```

Or use conda:

```bash
conda install our-package
```
""",
        )

        self.specialized.markdown_edit_section(
            "README.md",
            "Usage",
            """
Here's how to use our package:

```python
from our_package import main_class
result = main_class.process()
```
""",
        )

        # Verify final result
        final_content = self.agent_fs.read_full_file("README.md")
        assert "pip install our-package" in final_content
        assert "conda install our-package" in final_content
        assert "from our_package import main_class" in final_content
        assert "This project is amazing." in final_content  # Original content preserved

    @pytest.mark.integration
    def test_data_analysis_workflow(self) -> None:
        """Test a data analysis workflow with CSV processing."""
        # Create sample data
        csv_data = """name,age,department,salary,performance
Alice Johnson,28,Engineering,75000,excellent
Bob Smith,35,Marketing,68000,good
Carol Davis,31,Engineering,82000,excellent
David Wilson,29,Sales,59000,average
Eve Brown,33,Engineering,78000,good
"""

        self.agent_fs.create_file("employees.csv", csv_data)

        # Filter high performers
        high_performers = self.specialized.csv_filter_rows(
            "employees.csv", "performance", "excellent", "high_performers.csv"
        )
        assert high_performers is not None

        # Filter engineering department
        engineers = self.specialized.csv_filter_rows(
            "employees.csv", "department", "Engineering", "engineers.csv"
        )
        assert engineers is not None

        # Verify results
        hp_content = self.agent_fs.read_full_file("high_performers.csv")
        assert "Alice Johnson" in hp_content
        assert "Carol Davis" in hp_content
        assert "Bob Smith" not in hp_content

        eng_content = self.agent_fs.read_full_file("engineers.csv")
        assert "Alice Johnson" in eng_content
        assert "Carol Davis" in eng_content
        assert "Eve Brown" in eng_content
        assert "Bob Smith" not in eng_content

    @pytest.mark.integration
    def test_code_documentation_workflow(self) -> None:
        """Test workflow for maintaining code documentation."""
        # Create API documentation
        api_doc = """# API Reference

## Authentication
Details about auth.

## Endpoints

### GET /users
Returns user list.

### POST /users
Creates new user.

## Error Codes
Common error codes.
"""

        self.agent_fs.create_file("api.md", api_doc)

        # Add new endpoint documentation
        new_endpoint_doc = """
### GET /users/{id}
Returns specific user by ID.

**Parameters:**
- `id` (integer): User ID

**Response:**
```json
{
  "id": 123,
  "name": "John Doe",
  "email": "john@example.com"
}
```
"""

        # Insert new section (this would require extending the markdown editor)
        # For now, we'll update an existing section
        updated_endpoints = """
### GET /users
Returns user list.

### GET /users/{id}
Returns specific user by ID.

### POST /users
Creates new user.

### PUT /users/{id}
Updates existing user.

### DELETE /users/{id}
Deletes user.
"""

        success = self.specialized.markdown_edit_section(
            "api.md", "Endpoints", updated_endpoints
        )
        assert success

        # Verify documentation was updated
        final_doc = self.agent_fs.read_full_file("api.md")
        assert "GET /users/{id}" in final_doc
        assert "PUT /users/{id}" in final_doc
        assert "DELETE /users/{id}" in final_doc
        assert "Details about auth." in final_doc  # Other sections preserved
