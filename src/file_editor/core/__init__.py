"""Core file editing modules."""

from .mmap_editor import MmapEditor, quick_edit, quick_find_replace
from .safety import (
    PerformanceMonitor,
    ProductionFileEditor,
    RetryableOperation,
    SafeFileOperation,
    performance_monitor,
    production_safe_edit,
    safe_edit_context,
)
from .seek_editor import LineIndexedFile, SeekEditor, SparseFileEditor
from .stream_editor import (
    ContextAwareStreamEditor,
    StreamEditor,
    stream_copy_with_transform,
)

__all__ = [
    # Memory-mapped editing
    "MmapEditor",
    "quick_edit",
    "quick_find_replace",
    # Streaming editing
    "StreamEditor",
    "ContextAwareStreamEditor",
    "stream_copy_with_transform",
    # Seek-based editing
    "SeekEditor",
    "LineIndexedFile",
    "SparseFileEditor",
    # Safety mechanisms
    "SafeFileOperation",
    "safe_edit_context",
    "production_safe_edit",
    "RetryableOperation",
    "PerformanceMonitor",
    "ProductionFileEditor",
    "performance_monitor",
]
