"""Comprehensive tests for streaming file operations."""
import tempfile
from pathlib import Path
from typing import Any

import pytest
from file_editor.core.stream_editor import (
    ContextAwareStreamEditor,
    StreamEditor,
    parallel_chunk_processor,
    stream_copy_with_transform,
)
from hypothesis import given
from hypothesis import strategies as st


class TestStreamEditor:
    """Test streaming file editor functionality."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.txt"

    def teardown_method(self) -> None:
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_read_chunks_binary(self) -> None:
        """Test reading file in binary chunks."""
        test_data = b"A" * 1000 + b"B" * 1000 + b"C" * 1000
        self.test_file.write_bytes(test_data)

        editor = StreamEditor(self.test_file, chunk_size=500)
        chunks = list(editor.read_chunks(binary=True))

        # Should have 6 chunks of 500 bytes each
        assert len(chunks) == 6
        assert all(len(chunk) == 500 for chunk in chunks)
        assert chunks[0] == b"A" * 500
        assert chunks[1] == b"A" * 500
        assert chunks[2] == b"B" * 500

    def test_read_chunks_text(self) -> None:
        """Test reading file in text chunks."""
        test_data = "Hello " * 200  # 1200 characters
        self.test_file.write_text(test_data)

        editor = StreamEditor(self.test_file, chunk_size=400)
        chunks = list(editor.read_chunks(binary=False))

        # Should have 3 chunks
        assert len(chunks) == 3
        assert chunks[0] == "Hello " * 66 + "Hell"  # 400 chars
        assert chunks[1] == "o " + "Hello " * 66 + "He"  # 400 chars
        assert len(chunks[2]) == 400  # Remaining chars

    def test_read_lines_individual(self) -> None:
        """Test reading lines individually."""
        lines = [f"Line {i}" for i in range(100)]
        test_data = "\n".join(lines)
        self.test_file.write_text(test_data)

        editor = StreamEditor(self.test_file)
        read_lines = list(editor.read_lines())

        assert len(read_lines) == 100
        for i, line in enumerate(read_lines):
            assert line.strip() == f"Line {i}"

    def test_read_lines_batched(self) -> None:
        """Test reading lines in batches."""
        lines = [f"Line {i}" for i in range(100)]
        test_data = "\n".join(lines)
        self.test_file.write_text(test_data)

        editor = StreamEditor(self.test_file)
        batches = list(editor.read_lines(batch_size=10))

        assert len(batches) == 10
        for batch in batches:
            assert len(batch) == 10

        # Verify first batch
        assert batches[0][0].strip() == "Line 0"
        assert batches[0][9].strip() == "Line 9"

    def test_process_chunks(self) -> None:
        """Test chunk processing with transformation."""
        test_data = "hello world " * 100
        self.test_file.write_text(test_data)

        def uppercase_processor(chunk: str) -> str:
            return chunk.upper()

        editor = StreamEditor(self.test_file)
        output_path = editor.process_chunks(uppercase_processor, binary=False)

        assert output_path is not None
        result = output_path.read_text()
        assert result == test_data.upper()

        # Clean up
        output_path.unlink()

    def test_process_lines(self) -> None:
        """Test line processing with transformation."""
        lines = [f"line {i}" for i in range(50)]
        test_data = "\n".join(lines)
        self.test_file.write_text(test_data)

        def capitalize_processor(line: str) -> str:
            return line.capitalize()

        editor = StreamEditor(self.test_file)
        output_path = editor.process_lines(capitalize_processor)

        assert output_path is not None
        result_lines = output_path.read_text().strip().split("\n")
        assert len(result_lines) == 50
        assert result_lines[0] == "Line 0"
        assert result_lines[49] == "Line 49"

        # Clean up
        output_path.unlink()

    def test_filter_lines(self) -> None:
        """Test line filtering functionality."""
        lines = [f"line {i}" for i in range(100)]
        test_data = "\n".join(lines)
        self.test_file.write_text(test_data)

        def even_filter(line: str) -> bool:
            num = int(line.split()[1])
            return num % 2 == 0

        editor = StreamEditor(self.test_file)
        output_path = editor.filter_lines(even_filter)

        assert output_path is not None
        result_lines = output_path.read_text().strip().split("\n")
        assert len(result_lines) == 50  # Half the lines
        assert "line 0" in result_lines
        assert "line 2" in result_lines
        assert "line 1" not in result_lines

        # Clean up
        output_path.unlink()

    def test_count_lines(self) -> None:
        """Test line counting functionality."""
        lines = [f"Line {i}" for i in range(1000)]
        test_data = "\n".join(lines)
        self.test_file.write_text(test_data)

        editor = StreamEditor(self.test_file)
        count = editor.count_lines()
        assert count == 1000

    def test_head_operation(self) -> None:
        """Test getting first n lines."""
        lines = [f"Line {i}" for i in range(100)]
        test_data = "\n".join(lines)
        self.test_file.write_text(test_data)

        editor = StreamEditor(self.test_file)

        # Test default head (10 lines)
        head_lines = editor.head()
        assert len(head_lines) == 10
        assert head_lines[0] == "Line 0"
        assert head_lines[9] == "Line 9"

        # Test custom head size
        head_lines = editor.head(25)
        assert len(head_lines) == 25
        assert head_lines[24] == "Line 24"

    def test_tail_operation(self) -> None:
        """Test getting last n lines."""
        lines = [f"Line {i}" for i in range(100)]
        test_data = "\n".join(lines)
        self.test_file.write_text(test_data)

        editor = StreamEditor(self.test_file)

        # Test default tail (10 lines)
        tail_lines = editor.tail()
        assert len(tail_lines) == 10
        assert tail_lines[0] == "Line 90"
        assert tail_lines[9] == "Line 99"

        # Test custom tail size
        tail_lines = editor.tail(25)
        assert len(tail_lines) == 25
        assert tail_lines[0] == "Line 75"
        assert tail_lines[24] == "Line 99"

    def test_grep_functionality(self) -> None:
        """Test grep-like search functionality."""
        lines = [
            "Hello World",
            "This is a test",
            "hello universe",
            "HELLO GALAXY",
            "Goodbye World",
        ]
        test_data = "\n".join(lines)
        self.test_file.write_text(test_data)

        editor = StreamEditor(self.test_file)

        # Case sensitive search
        results = list(editor.grep("Hello"))
        assert len(results) == 1
        assert results[0] == (1, "Hello World")

        # Case insensitive search
        results = list(editor.grep("hello", case_sensitive=False))
        assert len(results) == 3
        line_numbers = [r[0] for r in results]
        assert 1 in line_numbers  # Hello World
        assert 3 in line_numbers  # hello universe
        assert 4 in line_numbers  # HELLO GALAXY

    def test_empty_file_handling(self) -> None:
        """Test handling of empty files."""
        self.test_file.touch()

        editor = StreamEditor(self.test_file)

        # All operations should handle empty file gracefully
        assert editor.count_lines() == 0
        assert editor.head() == []
        assert editor.tail() == []
        assert list(editor.read_chunks()) == []
        assert list(editor.read_lines()) == []
        assert list(editor.grep("test")) == []

    @pytest.mark.slow
    def test_large_file_processing(self) -> None:
        """Test processing of large files."""
        # Create 1MB file with 100,000 lines
        lines = [f"Line {i:06d}" for i in range(100000)]
        test_data = "\n".join(lines)
        self.test_file.write_text(test_data)

        editor = StreamEditor(self.test_file, chunk_size=8192)

        # Test that we can process without loading everything into memory
        count = editor.count_lines()
        assert count == 100000

        # Test batch processing
        total_processed = 0
        for batch in editor.read_lines(batch_size=1000):
            total_processed += len(batch)
        assert total_processed == 100000

    @pytest.mark.performance
    def test_chunk_processing_performance(self, benchmark: Any) -> None:
        """Benchmark chunk processing performance."""
        # Create 1MB test file
        test_data = "0123456789\n" * 100000  # ~1MB
        self.test_file.write_text(test_data)

        def process_chunks() -> int:
            editor = StreamEditor(self.test_file, chunk_size=8192)
            total_size = 0
            for chunk in editor.read_chunks(binary=False):
                total_size += len(chunk)
            return total_size

        result = benchmark(process_chunks)
        assert result > 1000000  # Should be around 1MB

    @given(
        lines=st.lists(st.text(min_size=1, max_size=100), min_size=1, max_size=100),
        chunk_size=st.integers(min_value=64, max_value=8192),
    )
    def test_property_based_chunk_reading(
        self, lines: list[str], chunk_size: int
    ) -> None:
        """Property-based testing for chunk reading."""
        test_data = "\n".join(lines)
        self.test_file.write_text(test_data)

        editor = StreamEditor(self.test_file, chunk_size=chunk_size)

        # Reading all chunks should give us the complete file
        chunks = list(editor.read_chunks(binary=False))
        reconstructed = "".join(chunks)
        assert reconstructed == test_data


class TestContextAwareStreamEditor:
    """Test context-aware streaming editor."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.txt"

    def teardown_method(self) -> None:
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_context_aware_processing(self) -> None:
        """Test processing with context awareness."""
        lines = [
            "function start",
            "  line 1",
            "  line 2",
            "  important line",
            "  line 4",
            "function end",
            "another function start",
            "  different line",
            "another function end",
        ]
        test_data = "\n".join(lines)
        self.test_file.write_text(test_data)

        def needs_processing(line: str, context: Any) -> bool:
            return "important" in line

        def transform_with_context(line: str, context: Any, pending: list[str]) -> str:
            return f"PROCESSED: {line}"

        editor = ContextAwareStreamEditor(self.test_file, context_lines=2)
        output_path = editor.process_with_context(
            needs_processing, transform_with_context
        )

        assert output_path is not None
        result = output_path.read_text()

        # Should have processed the important line
        assert "PROCESSED: " in result
        assert "important" in result

        # Clean up
        output_path.unlink()


class TestStreamHelpers:
    """Test stream helper functions."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self) -> None:
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_stream_copy_with_transform(self) -> None:
        """Test stream copy with transformation."""
        source = Path(self.temp_dir) / "source.bin"
        dest = Path(self.temp_dir) / "dest.bin"

        test_data = b"hello world " * 1000
        source.write_bytes(test_data)

        def uppercase_transform(chunk: bytes) -> bytes:
            return chunk.upper()

        stream_copy_with_transform(source, dest, uppercase_transform, chunk_size=1024)

        result = dest.read_bytes()
        assert result == test_data.upper()

    def test_parallel_chunk_processor(self) -> None:
        """Test parallel chunk processor."""
        test_file = Path(self.temp_dir) / "test.bin"
        test_data = b"ABCDEFGHIJKLMNOP" * 100  # 1600 bytes
        test_file.write_bytes(test_data)

        def lowercase_processor(offset: int, chunk: bytes) -> bytes:
            return chunk.lower()

        results = list(
            parallel_chunk_processor(
                test_file, lowercase_processor, chunk_size=400, num_chunks=4
            )
        )

        assert len(results) == 4

        # Check that we got the right offsets and processed data
        offsets = [offset for offset, _ in results]
        assert offsets == [0, 400, 800, 1200]

        # Check that data was processed correctly
        for offset, processed_chunk in results:
            assert processed_chunk == processed_chunk.lower()
            assert len(processed_chunk) == 400

    def test_memory_efficiency(self) -> None:
        """Test that streaming operations don't load entire file into memory."""
        # Create a large file
        large_file = Path(self.temp_dir) / "large.txt"

        # Write 10MB of data
        chunk = "A" * 1024  # 1KB
        with open(large_file, "w") as f:
            for _ in range(10 * 1024):  # 10MB total
                f.write(chunk)

        editor = StreamEditor(large_file, chunk_size=8192)

        # Process the file in chunks - this should not consume 10MB of RAM
        total_chars = 0
        max_chunk_size = 0

        for chunk in editor.read_chunks(binary=False):
            total_chars += len(chunk)
            max_chunk_size = max(max_chunk_size, len(chunk))

        # Verify we processed the whole file
        assert total_chars == 10 * 1024 * 1024  # 10MB

        # Verify we never loaded more than chunk_size at once
        assert max_chunk_size <= 8192

    def test_file_not_found_handling(self) -> None:
        """Test handling of non-existent files."""
        nonexistent = Path(self.temp_dir) / "nonexistent.txt"

        editor = StreamEditor(nonexistent)

        with pytest.raises(FileNotFoundError):
            list(editor.read_chunks())

        with pytest.raises(FileNotFoundError):
            list(editor.read_lines())

        with pytest.raises(FileNotFoundError):
            editor.count_lines()

    def test_custom_output_path(self) -> None:
        """Test using custom output paths for processing."""
        test_file = Path(self.temp_dir) / "input.txt"
        output_file = Path(self.temp_dir) / "custom_output.txt"

        test_data = "hello world\ntest line\nanother line"
        test_file.write_text(test_data)

        def uppercase_processor(line: str) -> str:
            return line.upper()

        editor = StreamEditor(test_file)
        result_path = editor.process_lines(uppercase_processor, output_file)

        assert result_path == output_file
        assert output_file.exists()

        result = output_file.read_text()
        assert "HELLO WORLD" in result
        assert "TEST LINE" in result

    def test_none_returning_processor(self) -> None:
        """Test processor that returns None to skip lines."""
        lines = [f"line {i}" for i in range(10)]
        test_data = "\n".join(lines)
        self.test_file.write_text(test_data)

        def skip_even_processor(line: str) -> str | None:
            num = int(line.split()[1])
            return line if num % 2 == 1 else None

        editor = StreamEditor(self.test_file)
        output_path = editor.process_lines(skip_even_processor)

        assert output_path is not None
        result_lines = output_path.read_text().strip().split("\n")

        # Should only have odd-numbered lines
        assert len(result_lines) == 5
        assert "line 1" in result_lines
        assert "line 3" in result_lines
        assert "line 0" not in result_lines

        # Clean up
        output_path.unlink()


class TestErrorHandling:
    """Test error handling in streaming operations."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self) -> None:
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_permission_denied_handling(self) -> None:
        """Test handling of permission denied errors."""
        # Create a file and make it unreadable
        test_file = Path(self.temp_dir) / "unreadable.txt"
        test_file.write_text("test content")
        test_file.chmod(0o000)  # No permissions

        editor = StreamEditor(test_file)

        try:
            with pytest.raises(PermissionError):
                list(editor.read_chunks())
        finally:
            # Restore permissions for cleanup
            test_file.chmod(0o666)

    def test_disk_full_simulation(self) -> None:
        """Test handling when disk becomes full during write operations."""
        # This test is difficult to implement portably
        # In a real scenario, you'd mock the file operations
        # For now, we'll test the error propagation structure

        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_text("test content")

        def failing_processor(line: str) -> str:
            raise OSError("No space left on device")

        editor = StreamEditor(test_file)

        with pytest.raises(OSError):
            editor.process_lines(failing_processor)

    def test_invalid_chunk_size(self) -> None:
        """Test handling of invalid chunk sizes."""
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_text("test content")

        # Chunk size must be positive
        with pytest.raises((ValueError, TypeError)):
            StreamEditor(test_file, chunk_size=0)

        with pytest.raises((ValueError, TypeError)):
            StreamEditor(test_file, chunk_size=-1)
