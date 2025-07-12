"""Basic functionality tests for file_editor package."""
import tempfile
from pathlib import Path

import pytest
from file_editor import AgentFileSystem, MarkdownEditor, MmapEditor, TextEditor


class TestAgentFileSystem:
    """Test the agent-friendly file system interface."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.agent_fs = AgentFileSystem(self.temp_dir)

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_create_and_read_file(self):
        """Test basic file creation and reading."""
        content = "Hello, World!\nThis is a test file."

        # Create file
        success = self.agent_fs.create_file("test.txt", content)
        assert success

        # Check file exists
        assert self.agent_fs.file_exists("test.txt")

        # Read full file
        read_content = self.agent_fs.read_full_file("test.txt")
        assert read_content == content

    def test_read_file_section(self):
        """Test reading specific file sections."""
        lines = ["Line 1", "Line 2", "Line 3", "Line 4", "Line 5"]
        content = "\n".join(lines)

        self.agent_fs.create_file("test.txt", content)

        # Read lines 2-4
        section = self.agent_fs.read_file_section("test.txt", 2, 4)
        expected = "Line 2\nLine 3\nLine 4"
        assert section == expected

    def test_modify_file_section(self):
        """Test modifying file sections."""
        original = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        self.agent_fs.create_file("test.txt", original)

        # Replace lines 2-3
        success = self.agent_fs.modify_file_section(
            "test.txt", 2, 3, "New Line 2\nNew Line 3"
        )
        assert success

        # Verify change
        content = self.agent_fs.read_full_file("test.txt")
        expected = "Line 1\nNew Line 2\nNew Line 3\nLine 4\nLine 5"
        assert content == expected

    def test_search_in_file(self):
        """Test file search functionality."""
        content = "Hello World\nThis is a test\nHello again\nFinal line"
        self.agent_fs.create_file("test.txt", content)

        # Search for "Hello"
        results = self.agent_fs.search_in_file("test.txt", "Hello")
        assert len(results) == 2
        assert results[0][0] == 1  # Line number
        assert "Hello World" in results[0][1]  # Line content
        assert results[1][0] == 3
        assert "Hello again" in results[1][1]

    def test_file_stats(self):
        """Test file statistics."""
        content = "Hello world\nThis is a test\nWith multiple lines"
        self.agent_fs.create_file("test.txt", content)

        stats = self.agent_fs.get_file_stats("test.txt")
        assert stats is not None
        assert stats["lines"] == 3
        assert stats["words"] == 9
        assert stats["characters"] > 0


class TestMarkdownEditor:
    """Test markdown-specific editing functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.md"

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_section_editing(self):
        """Test markdown section editing."""
        markdown_content = """# Main Title

## Section 1
This is section 1 content.

## Section 2
This is section 2 content.

## Section 3
This is section 3 content.
"""

        # Create markdown file
        with open(self.test_file, "w") as f:
            f.write(markdown_content)

        # Edit section 2
        editor = MarkdownEditor(self.test_file)
        success = editor.edit_section_streaming(
            "Section 2", "This is NEW section 2 content."
        )
        assert success

        # Verify change
        with open(self.test_file) as f:
            content = f.read()

        assert "This is NEW section 2 content." in content
        assert "This is section 1 content." in content  # Other sections unchanged
        assert "This is section 3 content." in content

    def test_section_insertion(self):
        """Test inserting new markdown sections."""
        markdown_content = """# Main Title

## Section 1
Content 1

## Section 2
Content 2
"""

        with open(self.test_file, "w") as f:
            f.write(markdown_content)

        editor = MarkdownEditor(self.test_file)
        success = editor.insert_section(
            "New Section", "New content here", level=2, after_section="Section 1"
        )
        assert success

        with open(self.test_file) as f:
            content = f.read()

        assert "## New Section" in content
        assert "New content here" in content


class TestMemoryMappedEditor:
    """Test memory-mapped file operations."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.bin"

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_basic_operations(self):
        """Test basic memory-mapped operations."""
        # Create test file
        test_data = b"Hello, World! This is a test file for memory mapping."
        with open(self.test_file, "wb") as f:
            f.write(test_data)

        # Test memory-mapped editing
        with MmapEditor(self.test_file) as editor:
            # Read slice
            slice_data = editor.read_slice(0, 5)
            assert slice_data == b"Hello"

            # Find pattern
            pos = editor.find(b"World")
            assert pos == 7

            # Replace pattern (same length)
            pos = editor.replace(b"World", b"Earth")
            assert pos == 7

            editor.flush()

        # Verify change
        with open(self.test_file, "rb") as f:
            content = f.read()

        assert b"Hello, Earth!" in content


class TestTextEditor:
    """Test text editing functionality."""

    def setup_method(self):
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.txt"

    def teardown_method(self):
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_line_operations(self):
        """Test line-based operations."""
        content = "Line 1\nLine 2\nLine 3\nLine 4\nLine 5"
        with open(self.test_file, "w") as f:
            f.write(content)

        editor = TextEditor(self.test_file)

        # Test line insertion
        success = editor.insert_lines(3, ["New Line A", "New Line B"])
        assert success

        # Verify insertion
        with open(self.test_file) as f:
            lines = f.read().split("\n")

        assert "New Line A" in lines
        assert "New Line B" in lines

        # Test line deletion
        success = editor.delete_lines(2, 3)  # Delete lines 2-3
        assert success

        # Test find and replace
        success = editor.replace_in_lines("Line 1", "Modified Line 1")
        assert success


if __name__ == "__main__":
    pytest.main([__file__])
