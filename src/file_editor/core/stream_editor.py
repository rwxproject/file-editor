"""Streaming file editor for memory-efficient sequential processing."""
import os
from pathlib import Path
from typing import Union, Iterator, Callable, Optional, BinaryIO, TextIO
from collections import deque
import itertools
import logging

logger = logging.getLogger(__name__)


class StreamEditor:
    """Streaming file editor for memory-efficient sequential processing.
    
    This class provides memory-bounded file processing using generators and
    streaming techniques. It's particularly efficient for:
    - Sequential processing of large files
    - Maintaining constant memory usage
    - Processing files larger than available RAM
    - Line-by-line or chunk-based transformations
    """
    
    def __init__(self, file_path: Union[str, Path], chunk_size: int = 8192):
        """Initialize streaming editor.
        
        Args:
            file_path: Path to the file to edit
            chunk_size: Size of chunks to read/process (default 8KB)
        """
        self.file_path = Path(file_path)
        self.chunk_size = chunk_size
        
    def read_chunks(self, binary: bool = True) -> Iterator[Union[bytes, str]]:
        """Read file in chunks.
        
        Args:
            binary: Whether to read in binary mode
            
        Yields:
            Chunks of file content
        """
        mode = 'rb' if binary else 'r'
        with open(self.file_path, mode) as f:
            while True:
                chunk = f.read(self.chunk_size)
                if not chunk:
                    break
                yield chunk
                
    def read_lines(self, batch_size: Optional[int] = None) -> Iterator[Union[str, list[str]]]:
        """Read file line by line or in batches.
        
        Args:
            batch_size: If provided, yield batches of lines instead of individual lines
            
        Yields:
            Individual lines or batches of lines
        """
        with open(self.file_path, 'r') as f:
            if batch_size is None:
                yield from f
            else:
                while True:
                    batch = list(itertools.islice(f, batch_size))
                    if not batch:
                        break
                    yield batch
                    
    def process_chunks(self, processor: Callable[[Union[bytes, str]], Union[bytes, str]], 
                      output_path: Optional[Union[str, Path]] = None, 
                      binary: bool = True) -> Optional[Path]:
        """Process file chunks with a transformation function.
        
        Args:
            processor: Function to transform each chunk
            output_path: Output file path (if None, creates temp file)
            binary: Whether to process in binary mode
            
        Returns:
            Path to output file
        """
        if output_path is None:
            output_path = self.file_path.with_suffix('.tmp')
        
        output_path = Path(output_path)
        mode = 'wb' if binary else 'w'
        
        with open(output_path, mode) as out:
            for chunk in self.read_chunks(binary):
                processed = processor(chunk)
                if processed:
                    out.write(processed)
                    
        return output_path
        
    def process_lines(self, processor: Callable[[str], Optional[str]], 
                     output_path: Optional[Union[str, Path]] = None) -> Optional[Path]:
        """Process file line by line with a transformation function.
        
        Args:
            processor: Function to transform each line (return None to skip line)
            output_path: Output file path (if None, creates temp file)
            
        Returns:
            Path to output file
        """
        if output_path is None:
            output_path = self.file_path.with_suffix('.tmp')
            
        output_path = Path(output_path)
        
        with open(output_path, 'w') as out:
            for line in self.read_lines():
                processed = processor(line)
                if processed is not None:
                    out.write(processed)
                    
        return output_path
        
    def filter_lines(self, predicate: Callable[[str], bool], 
                    output_path: Optional[Union[str, Path]] = None) -> Optional[Path]:
        """Filter lines based on a predicate function.
        
        Args:
            predicate: Function to test each line
            output_path: Output file path
            
        Returns:
            Path to output file
        """
        return self.process_lines(
            lambda line: line if predicate(line) else None,
            output_path
        )
        
    def count_lines(self) -> int:
        """Count lines in file efficiently."""
        count = 0
        for _ in self.read_lines():
            count += 1
        return count
        
    def head(self, n: int = 10) -> list[str]:
        """Get first n lines of file."""
        lines = []
        for i, line in enumerate(self.read_lines()):
            if i >= n:
                break
            lines.append(line.rstrip('\n'))
        return lines
        
    def tail(self, n: int = 10) -> list[str]:
        """Get last n lines of file efficiently using deque."""
        return list(deque(
            (line.rstrip('\n') for line in self.read_lines()), 
            maxlen=n
        ))
        
    def grep(self, pattern: str, case_sensitive: bool = True) -> Iterator[tuple[int, str]]:
        """Search for lines containing pattern.
        
        Args:
            pattern: Pattern to search for
            case_sensitive: Whether search is case sensitive
            
        Yields:
            Tuples of (line_number, line_content)
        """
        if not case_sensitive:
            pattern = pattern.lower()
            
        for line_num, line in enumerate(self.read_lines(), 1):
            search_line = line if case_sensitive else line.lower()
            if pattern in search_line:
                yield (line_num, line.rstrip('\n'))
                
                
class ContextAwareStreamEditor(StreamEditor):
    """Stream editor with context awareness for complex transformations."""
    
    def __init__(self, file_path: Union[str, Path], chunk_size: int = 8192, context_lines: int = 2):
        """Initialize context-aware stream editor.
        
        Args:
            file_path: Path to the file to edit
            chunk_size: Size of chunks to read/process
            context_lines: Number of context lines to maintain
        """
        super().__init__(file_path, chunk_size)
        self.context_lines = context_lines
        
    def process_with_context(self, condition_func: Callable[[str, deque], bool],
                           transform_func: Callable[[str, deque, list], str],
                           output_path: Optional[Union[str, Path]] = None) -> Optional[Path]:
        """Process lines with surrounding context awareness.
        
        Args:
            condition_func: Function to check if line needs transformation
            transform_func: Function to transform line with context
            output_path: Output file path
            
        Returns:
            Path to output file
        """
        if output_path is None:
            output_path = self.file_path.with_suffix('.tmp')
            
        output_path = Path(output_path)
        context_buffer = deque(maxlen=self.context_lines)
        pending_lines = []
        
        with open(output_path, 'w') as out:
            for line in self.read_lines():
                if condition_func(line, context_buffer):
                    # Transform with context
                    modified = transform_func(line, context_buffer, pending_lines)
                    pending_lines.append(modified)
                else:
                    # Flush pending and add current
                    for pending in pending_lines:
                        out.write(pending)
                    pending_lines = []
                    out.write(line)
                    
                context_buffer.append(line)
                
            # Flush remaining pending lines
            for pending in pending_lines:
                out.write(pending)
                
        return output_path
        
        
def stream_copy_with_transform(source: Union[str, Path], 
                             dest: Union[str, Path],
                             transform: Callable[[bytes], bytes],
                             chunk_size: int = 65536):
    """Copy file with streaming transformation.
    
    Args:
        source: Source file path
        dest: Destination file path
        transform: Transformation function for each chunk
        chunk_size: Size of chunks to process
    """
    source = Path(source)
    dest = Path(dest)
    
    with open(source, 'rb') as src, open(dest, 'wb') as dst:
        while True:
            chunk = src.read(chunk_size)
            if not chunk:
                break
            dst.write(transform(chunk))
            
            
def parallel_chunk_processor(file_path: Union[str, Path], 
                           processor: Callable[[int, bytes], bytes],
                           chunk_size: int = 1024 * 1024,
                           num_chunks: Optional[int] = None) -> Iterator[tuple[int, bytes]]:
    """Process file chunks with offset information.
    
    This generator allows for parallel-friendly processing by providing
    chunk offset information along with the data.
    
    Args:
        file_path: Path to file
        processor: Function taking (offset, chunk) and returning processed chunk
        chunk_size: Size of each chunk
        num_chunks: Maximum number of chunks to process
        
    Yields:
        Tuples of (offset, processed_chunk)
    """
    offset = 0
    chunks_processed = 0
    
    with open(file_path, 'rb') as f:
        while True:
            if num_chunks is not None and chunks_processed >= num_chunks:
                break
                
            chunk = f.read(chunk_size)
            if not chunk:
                break
                
            processed = processor(offset, chunk)
            yield (offset, processed)
            
            offset += len(chunk)
            chunks_processed += 1