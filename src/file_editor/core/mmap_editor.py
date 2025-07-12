"""Memory-mapped file editing for efficient random access operations."""
import mmap
import os
from pathlib import Path
from typing import Optional, Union, Callable
import logging

logger = logging.getLogger(__name__)


class MmapEditor:
    """Memory-mapped file editor for efficient random access operations.
    
    This class provides high-performance file editing capabilities using
    memory-mapped files, which are particularly efficient for:
    - Random access patterns
    - Large files that don't fit in memory
    - Frequent seek operations
    - In-place modifications
    """
    
    def __init__(self, file_path: Union[str, Path], mode: str = 'r+b'):
        """Initialize memory-mapped file editor.
        
        Args:
            file_path: Path to the file to edit
            mode: File open mode ('r+b' for read/write, 'rb' for read-only)
        """
        self.file_path = Path(file_path)
        self.mode = mode
        self._file = None
        self._mmap = None
        self._access_mode = None
        
    def __enter__(self):
        """Context manager entry."""
        self.open()
        return self
        
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.close()
        
    def open(self):
        """Open file and create memory mapping."""
        if self._file is not None:
            raise RuntimeError("File is already open")
            
        self._file = open(self.file_path, self.mode)
        self._access_mode = mmap.ACCESS_WRITE if '+' in self.mode else mmap.ACCESS_READ
        
        # Get file size
        self._file.seek(0, 2)  # Seek to end
        size = self._file.tell()
        self._file.seek(0)  # Return to start
        
        if size == 0:
            logger.warning(f"File {self.file_path} is empty, mmap not created")
            self._mmap = None
        else:
            self._mmap = mmap.mmap(self._file.fileno(), 0, access=self._access_mode)
            
    def close(self):
        """Close memory mapping and file."""
        if self._mmap is not None:
            self._mmap.close()
            self._mmap = None
            
        if self._file is not None:
            self._file.close()
            self._file = None
            
    def read_slice(self, start: int, end: Optional[int] = None) -> bytes:
        """Read a slice of the file.
        
        Args:
            start: Starting byte offset
            end: Ending byte offset (None for end of file)
            
        Returns:
            Bytes from the specified range
        """
        if self._mmap is None:
            raise RuntimeError("No memory mapping available")
            
        if end is None:
            return self._mmap[start:]
        return self._mmap[start:end]
        
    def write_slice(self, start: int, data: bytes) -> int:
        """Write data at a specific offset.
        
        Args:
            start: Starting byte offset
            data: Data to write
            
        Returns:
            Number of bytes written
        """
        if self._mmap is None:
            raise RuntimeError("No memory mapping available")
            
        if self._access_mode == mmap.ACCESS_READ:
            raise RuntimeError("File opened in read-only mode")
            
        end = start + len(data)
        if end > len(self._mmap):
            raise ValueError(f"Write would exceed file size ({end} > {len(self._mmap)})")
            
        self._mmap[start:end] = data
        return len(data)
        
    def find(self, pattern: bytes, start: int = 0, end: Optional[int] = None) -> int:
        """Find pattern in file.
        
        Args:
            pattern: Byte pattern to search for
            start: Starting offset for search
            end: Ending offset for search (None for end of file)
            
        Returns:
            Offset of pattern or -1 if not found
        """
        if self._mmap is None:
            raise RuntimeError("No memory mapping available")
            
        if end is None:
            return self._mmap.find(pattern, start)
        return self._mmap.find(pattern, start, end)
        
    def find_all(self, pattern: bytes, start: int = 0, end: Optional[int] = None) -> list[int]:
        """Find all occurrences of pattern in file.
        
        Args:
            pattern: Byte pattern to search for
            start: Starting offset for search
            end: Ending offset for search (None for end of file)
            
        Returns:
            List of offsets where pattern was found
        """
        positions = []
        pos = start
        
        while True:
            pos = self.find(pattern, pos, end)
            if pos == -1:
                break
            positions.append(pos)
            pos += len(pattern)
            
        return positions
        
    def replace(self, old: bytes, new: bytes, start: int = 0, end: Optional[int] = None) -> int:
        """Replace first occurrence of pattern.
        
        Args:
            old: Pattern to find
            new: Replacement pattern (must be same length)
            start: Starting offset
            end: Ending offset (None for end of file)
            
        Returns:
            Offset where replacement was made, or -1 if not found
        """
        if len(old) != len(new):
            raise ValueError("Replacement must be same length as original")
            
        pos = self.find(old, start, end)
        if pos != -1:
            self.write_slice(pos, new)
            
        return pos
        
    def replace_all(self, old: bytes, new: bytes, start: int = 0, end: Optional[int] = None) -> int:
        """Replace all occurrences of pattern.
        
        Args:
            old: Pattern to find
            new: Replacement pattern (must be same length)
            start: Starting offset
            end: Ending offset (None for end of file)
            
        Returns:
            Number of replacements made
        """
        if len(old) != len(new):
            raise ValueError("Replacement must be same length as original")
            
        positions = self.find_all(old, start, end)
        for pos in positions:
            self.write_slice(pos, new)
            
        return len(positions)
        
    def resize(self, new_size: int):
        """Resize the memory-mapped file.
        
        Args:
            new_size: New size in bytes
        """
        if self._mmap is None:
            raise RuntimeError("No memory mapping available")
            
        if self._access_mode == mmap.ACCESS_READ:
            raise RuntimeError("Cannot resize read-only mapping")
            
        # Close current mapping
        self._mmap.close()
        
        # Resize underlying file
        self._file.truncate(new_size)
        self._file.flush()
        
        # Recreate mapping
        if new_size > 0:
            self._mmap = mmap.mmap(self._file.fileno(), 0, access=self._access_mode)
        else:
            self._mmap = None
            
    def flush(self):
        """Flush changes to disk."""
        if self._mmap is not None:
            self._mmap.flush()
            
    def size(self) -> int:
        """Get file size."""
        if self._mmap is None:
            return 0
        return len(self._mmap)
        
    def apply_operation(self, operation: Callable[[mmap.mmap], None]):
        """Apply a custom operation to the memory mapping.
        
        Args:
            operation: Function that takes mmap object and performs operations
        """
        if self._mmap is None:
            raise RuntimeError("No memory mapping available")
            
        operation(self._mmap)
        
        
def quick_edit(file_path: Union[str, Path], offset: int, data: bytes):
    """Quick helper for simple edits.
    
    Args:
        file_path: Path to file
        offset: Byte offset to write at
        data: Data to write
    """
    with MmapEditor(file_path) as editor:
        editor.write_slice(offset, data)
        editor.flush()
        
        
def quick_find_replace(file_path: Union[str, Path], old: bytes, new: bytes) -> int:
    """Quick helper for find and replace operations.
    
    Args:
        file_path: Path to file
        old: Pattern to find
        new: Replacement pattern
        
    Returns:
        Number of replacements made
    """
    with MmapEditor(file_path) as editor:
        count = editor.replace_all(old, new)
        editor.flush()
        return count