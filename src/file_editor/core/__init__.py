"""Core file editing modules."""

from .mmap_editor import MmapEditor, quick_edit, quick_find_replace
from .stream_editor import StreamEditor, ContextAwareStreamEditor, stream_copy_with_transform
from .seek_editor import SeekEditor, LineIndexedFile, SparseFileEditor
from .safety import (
    SafeFileOperation, 
    safe_edit_context, 
    production_safe_edit,
    RetryableOperation,
    PerformanceMonitor,
    ProductionFileEditor,
    performance_monitor
)

__all__ = [
    # Memory-mapped editing
    'MmapEditor',
    'quick_edit', 
    'quick_find_replace',
    
    # Streaming editing
    'StreamEditor',
    'ContextAwareStreamEditor', 
    'stream_copy_with_transform',
    
    # Seek-based editing
    'SeekEditor',
    'LineIndexedFile',
    'SparseFileEditor',
    
    # Safety mechanisms
    'SafeFileOperation',
    'safe_edit_context',
    'production_safe_edit',
    'RetryableOperation',
    'PerformanceMonitor',
    'ProductionFileEditor',
    'performance_monitor',
]