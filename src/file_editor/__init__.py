"""Memory-efficient partial file editing library for Python with agent-friendly API."""

from .agent import AgentFileSystem, SpecializedAgentEditors
from .core import (
    MmapEditor,
    ProductionFileEditor,
    SeekEditor,
    StreamEditor,
    performance_monitor,
    safe_edit_context,
)
from .formats import CSVEditor, FastTextEditor, MarkdownEditor, TextEditor

__version__ = "0.1.0"

__all__ = [
    # Core editors
    "MmapEditor",
    "StreamEditor",
    "SeekEditor",
    "ProductionFileEditor",
    "safe_edit_context",
    "performance_monitor",
    # Format-specific editors
    "MarkdownEditor",
    "CSVEditor",
    "TextEditor",
    "FastTextEditor",
    # Agent interface
    "AgentFileSystem",
    "SpecializedAgentEditors",
]
