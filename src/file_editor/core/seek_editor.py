"""Seek-based file editor for targeted access patterns."""
import logging
import os
from collections.abc import Iterator
from pathlib import Path
from typing import BinaryIO, Optional, Union

logger = logging.getLogger(__name__)


class SeekEditor:
    """Seek-based file editor for precise positioning and targeted edits.

    This class provides efficient file editing using seek operations for:
    - Accessing specific file positions
    - Building indexes for rapid navigation
    - Modifying known locations
    - Sparse file operations
    """

    def __init__(self, file_path: Union[str, Path]):
        """Initialize seek-based editor.

        Args:
            file_path: Path to the file to edit
        """
        self.file_path = Path(file_path)
        self._file: Optional[BinaryIO] = None
        self._mode: Optional[str] = None

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()

    def open(self, mode: str = "r+b"):
        """Open file for seek operations.

        Args:
            mode: File open mode
        """
        if self._file is not None:
            raise RuntimeError("File is already open")

        self._mode = mode
        self._file = open(self.file_path, mode)

    def close(self):
        """Close the file."""
        if self._file is not None:
            self._file.close()
            self._file = None
            self._mode = None

    def seek(self, offset: int, whence: int = 0):
        """Seek to position in file.

        Args:
            offset: Byte offset
            whence: Reference point (0=start, 1=current, 2=end)
        """
        if self._file is None:
            raise RuntimeError("File not open")
        self._file.seek(offset, whence)

    def tell(self) -> int:
        """Get current file position."""
        if self._file is None:
            raise RuntimeError("File not open")
        return self._file.tell()

    def read_at(self, offset: int, size: int) -> bytes:
        """Read bytes at specific offset.

        Args:
            offset: Starting offset
            size: Number of bytes to read

        Returns:
            Bytes read from file
        """
        if self._file is None:
            self.open("rb")

        self.seek(offset)
        return self._file.read(size)

    def write_at(self, offset: int, data: bytes) -> int:
        """Write bytes at specific offset.

        Args:
            offset: Starting offset
            data: Data to write

        Returns:
            Number of bytes written
        """
        if self._file is None:
            self.open("r+b")
        elif "r+" not in self._mode and "w" not in self._mode and "a" not in self._mode:
            raise RuntimeError("File not open for writing")

        self.seek(offset)
        return self._file.write(data)

    def size(self) -> int:
        """Get file size."""
        if self._file is None:
            return self.file_path.stat().st_size

        current = self.tell()
        self.seek(0, 2)  # Seek to end
        size = self.tell()
        self.seek(current)  # Return to original position
        return size

    def truncate(self, size: Optional[int] = None):
        """Truncate file to specified size.

        Args:
            size: New file size (None for current position)
        """
        if self._file is None:
            raise RuntimeError("File not open")
        if "r+" not in self._mode and "w" not in self._mode and "a" not in self._mode:
            raise RuntimeError("File not open for writing")

        self._file.truncate(size)

    def insert_at(self, offset: int, data: bytes):
        """Insert data at offset, shifting existing content.

        Args:
            offset: Insertion point
            data: Data to insert
        """
        if self._file is None:
            self.open("r+b")

        # Read everything after insertion point
        self.seek(offset)
        remainder = self._file.read()

        # Write new data at insertion point
        self.seek(offset)
        self._file.write(data)

        # Write remainder
        self._file.write(remainder)

    def delete_range(self, start: int, end: int):
        """Delete bytes in range, shifting remaining content.

        Args:
            start: Start offset
            end: End offset (exclusive)
        """
        if self._file is None:
            self.open("r+b")

        # Read everything after deletion range
        self.seek(end)
        remainder = self._file.read()

        # Write remainder at start position
        self.seek(start)
        self._file.write(remainder)

        # Truncate file
        new_size = self.size() - (end - start)
        self.truncate(new_size)


class LineIndexedFile:
    """File with line-based indexing for O(1) line access."""

    def __init__(self, file_path: Union[str, Path]):
        """Initialize line-indexed file.

        Args:
            file_path: Path to the file
        """
        self.file_path = Path(file_path)
        self.line_positions: list[int] = []
        self._build_index()

    def _build_index(self):
        """Build line position index."""
        self.line_positions = [0]

        with open(self.file_path, "rb") as f:
            while True:
                line = f.readline()
                if not line:
                    break
                self.line_positions.append(f.tell())

        # Remove last position (EOF)
        if len(self.line_positions) > 1:
            self.line_positions.pop()

    def line_count(self) -> int:
        """Get number of lines in file."""
        return len(self.line_positions)

    def get_line(self, line_num: int) -> str:
        """Get specific line by number (0-indexed).

        Args:
            line_num: Line number to retrieve

        Returns:
            Line content
        """
        if line_num < 0 or line_num >= len(self.line_positions):
            raise IndexError(f"Line {line_num} out of range")

        with open(self.file_path, "rb") as f:
            f.seek(self.line_positions[line_num])
            return f.readline().decode("utf-8", errors="replace").rstrip("\n")

    def get_lines(self, start: int, end: int) -> list[str]:
        """Get range of lines.

        Args:
            start: Starting line number (inclusive)
            end: Ending line number (exclusive)

        Returns:
            List of lines
        """
        lines = []
        with open(self.file_path, "rb") as f:
            for i in range(start, min(end, len(self.line_positions))):
                f.seek(self.line_positions[i])
                line = f.readline().decode("utf-8", errors="replace").rstrip("\n")
                lines.append(line)
        return lines

    def iter_lines(self, start: int = 0, end: Optional[int] = None) -> Iterator[str]:
        """Iterate over lines efficiently.

        Args:
            start: Starting line number
            end: Ending line number (None for end of file)

        Yields:
            Line content
        """
        if end is None:
            end = len(self.line_positions)

        with open(self.file_path, "rb") as f:
            for i in range(start, min(end, len(self.line_positions))):
                f.seek(self.line_positions[i])
                yield f.readline().decode("utf-8", errors="replace").rstrip("\n")

    def replace_line(self, line_num: int, new_content: str):
        """Replace a specific line.

        Note: This creates a new file if line lengths differ.

        Args:
            line_num: Line number to replace
            new_content: New line content
        """
        if line_num < 0 or line_num >= len(self.line_positions):
            raise IndexError(f"Line {line_num} out of range")

        # Add newline if not present
        if not new_content.endswith("\n"):
            new_content += "\n"

        # For simplicity, rewrite entire file
        # In production, could optimize for same-length replacements
        temp_path = self.file_path.with_suffix(".tmp")

        with open(self.file_path, "rb") as src, open(temp_path, "wb") as dst:
            # Copy lines before target
            if line_num > 0:
                src.seek(0)
                dst.write(src.read(self.line_positions[line_num]))

            # Write new line
            dst.write(new_content.encode("utf-8"))

            # Skip old line and copy remainder
            if line_num < len(self.line_positions) - 1:
                src.seek(self.line_positions[line_num + 1])
                dst.write(src.read())

        # Replace original file
        os.replace(temp_path, self.file_path)

        # Rebuild index
        self._build_index()


class SparseFileEditor(SeekEditor):
    """Editor optimized for sparse files with large empty regions."""

    def find_data_regions(self, sample_size: int = 4096) -> list[tuple[int, int]]:
        """Find regions containing non-zero data.

        Args:
            sample_size: Size of samples to check

        Returns:
            List of (start, end) tuples for data regions
        """
        if self._file is None:
            self.open("rb")

        regions = []
        file_size = self.size()
        offset = 0
        in_region = False
        region_start = 0

        while offset < file_size:
            self.seek(offset)
            chunk = self._file.read(sample_size)

            if not chunk:
                break

            # Check if chunk contains non-zero data
            has_data = any(b != 0 for b in chunk)

            if has_data and not in_region:
                # Start of data region
                in_region = True
                region_start = offset
            elif not has_data and in_region:
                # End of data region
                in_region = False
                regions.append((region_start, offset))

            offset += len(chunk)

        # Handle case where file ends in data region
        if in_region:
            regions.append((region_start, file_size))

        return regions
