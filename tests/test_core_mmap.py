"""Comprehensive tests for memory-mapped file operations."""
import tempfile
import threading
import time
from pathlib import Path
from typing import Any

import pytest
from file_editor.core.mmap_editor import MmapEditor, quick_edit, quick_find_replace
from hypothesis import given
from hypothesis import strategies as st


class TestMmapEditor:
    """Test memory-mapped file editor functionality."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.bin"

    def teardown_method(self) -> None:
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_context_manager(self) -> None:
        """Test context manager functionality."""
        test_data = b"Hello, World! This is a test."
        self.test_file.write_bytes(test_data)

        with MmapEditor(self.test_file) as editor:
            assert editor._file is not None
            assert editor._mmap is not None
            data = editor.read_slice(0, 5)
            assert data == b"Hello"

        # After context exit, resources should be cleaned up
        assert editor._file is None
        assert editor._mmap is None

    def test_empty_file_handling(self) -> None:
        """Test handling of empty files."""
        self.test_file.touch()

        with MmapEditor(self.test_file) as editor:
            assert editor._mmap is None
            assert editor.size() == 0

            # Operations on empty file should raise appropriate errors
            with pytest.raises(RuntimeError, match="No memory mapping available"):
                editor.read_slice(0, 1)

    def test_read_slice_operations(self) -> None:
        """Test reading slices of different sizes and positions."""
        test_data = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ" * 100  # 2600 bytes
        self.test_file.write_bytes(test_data)

        with MmapEditor(self.test_file) as editor:
            # Test various slice operations
            assert editor.read_slice(0, 1) == b"A"
            assert editor.read_slice(25, 26) == b"Z"
            assert editor.read_slice(0, 26) == b"ABCDEFGHIJKLMNOPQRSTUVWXYZ"

            # Test reading to end of file
            end_data = editor.read_slice(2590)  # Last 10 bytes
            assert len(end_data) == 10

            # Test boundary conditions
            assert editor.read_slice(2599, 2600) == b"Z"

            # Test reading beyond file size
            beyond_data = editor.read_slice(2600, 2700)
            assert len(beyond_data) == 0

    def test_write_slice_operations(self) -> None:
        """Test writing to different positions and sizes."""
        test_data = b"A" * 1000
        self.test_file.write_bytes(test_data)

        with MmapEditor(self.test_file) as editor:
            # Test single byte write
            editor.write_slice(0, b"X")
            assert editor.read_slice(0, 1) == b"X"

            # Test multi-byte write
            editor.write_slice(10, b"HELLO")
            assert editor.read_slice(10, 15) == b"HELLO"

            # Test write at end
            editor.write_slice(995, b"WORLD")
            assert editor.read_slice(995, 1000) == b"WORLD"

            editor.flush()

        # Verify changes persisted
        with open(self.test_file, "rb") as f:
            content = f.read()
            assert content[0:1] == b"X"
            assert content[10:15] == b"HELLO"
            assert content[995:1000] == b"WORLD"

    def test_write_beyond_file_size(self) -> None:
        """Test writing beyond current file size raises error."""
        test_data = b"A" * 100
        self.test_file.write_bytes(test_data)

        with MmapEditor(self.test_file) as editor:
            # Should raise error when writing beyond file size
            with pytest.raises(ValueError, match="Write would exceed file size"):
                editor.write_slice(90, b"TOOLONGDATA")

    def test_find_operations(self) -> None:
        """Test pattern finding functionality."""
        test_data = b"Hello World! Hello Universe! Hello Galaxy!"
        self.test_file.write_bytes(test_data)

        with MmapEditor(self.test_file) as editor:
            # Test basic find
            pos = editor.find(b"Hello")
            assert pos == 0

            # Test find with start position
            pos = editor.find(b"Hello", start=1)
            assert pos == 13

            # Test find with start and end
            pos = editor.find(b"Hello", start=14, end=30)
            assert pos == 26

            # Test pattern not found
            pos = editor.find(b"NotFound")
            assert pos == -1

            # Test find_all
            positions = editor.find_all(b"Hello")
            assert positions == [0, 13, 26]

            # Test find_all with boundaries
            positions = editor.find_all(b"Hello", start=5, end=25)
            assert positions == [13]

    def test_replace_operations(self) -> None:
        """Test pattern replacement functionality."""
        test_data = b"Hello World! Hello World! Hello World!"
        self.test_file.write_bytes(test_data)

        with MmapEditor(self.test_file) as editor:
            # Test single replace
            pos = editor.replace(b"World", b"Earth")
            assert pos == 6
            assert editor.read_slice(0, 12) == b"Hello Earth!"

            # Test replace_all
            count = editor.replace_all(b"Hello", b"Greet")
            assert count == 3  # Should replace all 3 occurrences

            # Verify all replacements
            content = editor.read_slice(0)
            assert b"Greet Earth! Greet Earth! Greet Earth!" in content

    def test_replace_different_lengths_fails(self) -> None:
        """Test that replacement with different length fails."""
        test_data = b"Hello World!"
        self.test_file.write_bytes(test_data)

        with MmapEditor(self.test_file) as editor:
            with pytest.raises(ValueError, match="Replacement must be same length"):
                editor.replace(b"World", b"Universe")

    def test_resize_operations(self) -> None:
        """Test file resizing functionality."""
        test_data = b"A" * 1000
        self.test_file.write_bytes(test_data)

        with MmapEditor(self.test_file) as editor:
            assert editor.size() == 1000

            # Test growing file
            editor.resize(1500)
            assert editor.size() == 1500

            # Test shrinking file
            editor.resize(500)
            assert editor.size() == 500

            # Test resize to zero
            editor.resize(0)
            assert editor.size() == 0
            assert editor._mmap is None

    def test_read_only_mode(self) -> None:
        """Test read-only mode restrictions."""
        test_data = b"Read only test data"
        self.test_file.write_bytes(test_data)

        with MmapEditor(self.test_file, mode="rb") as editor:
            # Reading should work
            data = editor.read_slice(0, 4)
            assert data == b"Read"

            # Writing should fail
            with pytest.raises(RuntimeError, match="File opened in read-only mode"):
                editor.write_slice(0, b"Test")

            # Replace should fail
            with pytest.raises(RuntimeError, match="File opened in read-only mode"):
                editor.replace(b"Read", b"Test")

    def test_apply_operation(self) -> None:
        """Test custom operation application."""
        test_data = b"abcdefghijklmnop"
        self.test_file.write_bytes(test_data)

        def uppercase_operation(mm: Any) -> None:
            for i in range(len(mm)):
                if 97 <= mm[i] <= 122:  # lowercase letters
                    mm[i] = mm[i] - 32  # convert to uppercase

        with MmapEditor(self.test_file) as editor:
            editor.apply_operation(uppercase_operation)
            editor.flush()

        # Verify transformation
        result = self.test_file.read_bytes()
        assert result == b"ABCDEFGHIJKLMNOP"

    @pytest.mark.slow
    def test_large_file_operations(self) -> None:
        """Test operations on large files."""
        # Create 10MB file
        large_data = b"A" * (10 * 1024 * 1024)
        self.test_file.write_bytes(large_data)

        with MmapEditor(self.test_file) as editor:
            # Test reading from various positions
            assert editor.read_slice(0, 1) == b"A"
            assert editor.read_slice(5000000, 5000001) == b"A"
            assert editor.read_slice(-1)[0:1] == b"A"

            # Test writing at various positions
            editor.write_slice(1000000, b"X")
            editor.write_slice(5000000, b"Y")
            editor.write_slice(9000000, b"Z")

            # Verify writes
            assert editor.read_slice(1000000, 1000001) == b"X"
            assert editor.read_slice(5000000, 5000001) == b"Y"
            assert editor.read_slice(9000000, 9000001) == b"Z"

    @pytest.mark.performance
    def test_performance_random_access(self, benchmark: Any) -> None:
        """Benchmark random access performance."""
        # Create 1MB test file
        test_data = b"0123456789" * 102400  # ~1MB
        self.test_file.write_bytes(test_data)

        def random_reads() -> int:
            total = 0
            with MmapEditor(self.test_file) as editor:
                for i in range(1000):
                    pos = (i * 1337) % (len(test_data) - 10)
                    data = editor.read_slice(pos, pos + 10)
                    total += len(data)
            return total

        result = benchmark(random_reads)
        assert result == 10000  # 1000 reads of 10 bytes each

    def test_concurrent_read_access(self) -> None:
        """Test concurrent read access to same file."""
        test_data = b"Concurrent test data " * 1000
        self.test_file.write_bytes(test_data)

        results = []
        errors = []

        def read_worker(start_pos: int) -> None:
            try:
                with MmapEditor(self.test_file, mode="rb") as editor:
                    data = editor.read_slice(start_pos, start_pos + 20)
                    results.append(data)
                    time.sleep(0.1)  # Simulate some work
            except Exception as e:
                errors.append(e)

        # Start multiple concurrent readers
        threads = []
        for i in range(5):
            thread = threading.Thread(target=read_worker, args=(i * 100,))
            threads.append(thread)
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify no errors and all reads successful
        assert len(errors) == 0
        assert len(results) == 5
        for result in results:
            assert len(result) == 20

    @given(
        data=st.binary(min_size=1, max_size=1000),
        offset=st.integers(min_value=0, max_value=100),
        pattern=st.binary(min_size=1, max_size=10),
    )
    def test_property_based_operations(
        self, data: bytes, offset: int, pattern: bytes
    ) -> None:
        """Property-based testing for various operations."""
        if offset >= len(data):
            offset = len(data) - 1

        self.test_file.write_bytes(data)

        with MmapEditor(self.test_file) as editor:
            # Test that reading what we wrote gives us the same data
            read_data = editor.read_slice(0, len(data))
            assert read_data == data

            # Test pattern finding
            if pattern in data:
                pos = editor.find(pattern)
                assert pos != -1
                found_pattern = editor.read_slice(pos, pos + len(pattern))
                assert found_pattern == pattern
            else:
                pos = editor.find(pattern)
                assert pos == -1


class TestQuickHelpers:
    """Test quick helper functions."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.bin"

    def teardown_method(self) -> None:
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_quick_edit(self) -> None:
        """Test quick_edit helper function."""
        test_data = b"Hello World!"
        self.test_file.write_bytes(test_data)

        quick_edit(self.test_file, 6, b"Earth!")

        result = self.test_file.read_bytes()
        assert result == b"Hello Earth!"

    def test_quick_find_replace(self) -> None:
        """Test quick_find_replace helper function."""
        test_data = b"Hello World! Hello World!"
        self.test_file.write_bytes(test_data)

        count = quick_find_replace(self.test_file, b"World", b"Earth")
        assert count == 2

        result = self.test_file.read_bytes()
        assert result == b"Hello Earth! Hello Earth!"

    def test_quick_find_replace_no_matches(self) -> None:
        """Test quick_find_replace with no matches."""
        test_data = b"Hello World!"
        self.test_file.write_bytes(test_data)

        count = quick_find_replace(self.test_file, b"NotFound", b"Replacement")
        assert count == 0

        result = self.test_file.read_bytes()
        assert result == test_data  # Unchanged


class TestErrorHandling:
    """Test error handling and edge cases."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self) -> None:
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_nonexistent_file(self) -> None:
        """Test handling of non-existent files."""
        nonexistent = Path(self.temp_dir) / "nonexistent.bin"

        with pytest.raises(FileNotFoundError):
            with MmapEditor(nonexistent) as editor:
                pass

    def test_directory_instead_of_file(self) -> None:
        """Test handling when path points to directory."""
        directory = Path(self.temp_dir) / "subdir"
        directory.mkdir()

        with pytest.raises((PermissionError, IsADirectoryError)):
            with MmapEditor(directory) as editor:
                pass

    def test_permission_denied(self) -> None:
        """Test handling of permission denied errors."""
        # This test is platform-specific and may not work on all systems
        test_file = Path(self.temp_dir) / "readonly.bin"
        test_file.write_bytes(b"test")

        # Make file read-only
        test_file.chmod(0o444)

        try:
            with pytest.raises(PermissionError):
                with MmapEditor(test_file, mode="r+b") as editor:
                    editor.write_slice(0, b"x")
        finally:
            # Restore permissions for cleanup
            test_file.chmod(0o666)

    def test_double_open_error(self) -> None:
        """Test error when trying to open already opened editor."""
        test_file = Path(self.temp_dir) / "test.bin"
        test_file.write_bytes(b"test")

        editor = MmapEditor(test_file)
        editor.open()

        try:
            with pytest.raises(RuntimeError, match="File is already open"):
                editor.open()
        finally:
            editor.close()

    def test_operations_on_closed_editor(self) -> None:
        """Test operations on closed editor raise appropriate errors."""
        test_file = Path(self.temp_dir) / "test.bin"
        test_file.write_bytes(b"test")

        editor = MmapEditor(test_file)

        with pytest.raises(RuntimeError, match="No memory mapping available"):
            editor.read_slice(0, 1)

        with pytest.raises(RuntimeError, match="No memory mapping available"):
            editor.write_slice(0, b"x")
