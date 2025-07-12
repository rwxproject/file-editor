"""Memory-efficient partial file editing library for Python with agent-friendly API."""

from .core import (
    MmapEditor,
    StreamEditor, 
    SeekEditor,
    ProductionFileEditor,
    safe_edit_context,
    performance_monitor
)

from .formats import (
    MarkdownEditor,
    CSVEditor,
    TextEditor,
    FastTextEditor
)

from .agent import (
    AgentFileSystem,
    SpecializedAgentEditors
)

__version__ = "0.1.0"

__all__ = [
    # Core editors
    'MmapEditor',
    'StreamEditor',
    'SeekEditor', 
    'ProductionFileEditor',
    'safe_edit_context',
    'performance_monitor',
    
    # Format-specific editors
    'MarkdownEditor',
    'CSVEditor',
    'TextEditor',
    'FastTextEditor',
    
    # Agent interface
    'AgentFileSystem',
    'SpecializedAgentEditors',
]