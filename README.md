# File Editor

A memory-efficient partial file editing library for Python with agent-friendly API.

## Features

- **Memory Efficient**: Process files of any size without loading them entirely into memory
- **Multiple Strategies**: Memory-mapped files, streaming, and seek-based operations
- **Agent-Friendly**: High-level, safe abstractions perfect for AI agents
- **Format-Specific**: Specialized editors for Markdown, CSV, and text files
- **Production-Ready**: Atomic operations, file locking, automatic rollback, and comprehensive error handling
- **Performance Optimized**: Configurable chunk sizes, OS-specific optimizations, and performance monitoring

## Installation

Install using uv (recommended):

```bash
uv add file-editor
```

Or using pip:

```bash
pip install file-editor
```

For additional features, install with optional dependencies:

```bash
# For pandas-based CSV processing
uv add "file-editor[pandas]"

# For HDF5 support
uv add "file-editor[hdf5]"

# All optional dependencies
uv add "file-editor[all]"
```

## Quick Start

### Agent-Friendly Interface (Recommended for AI Agents)

```python
from file_editor import AgentFileSystem

# Create file system interface
fs = AgentFileSystem(workspace_dir="my_workspace")

# Create a file
fs.create_file("document.txt", "Hello, World!\nThis is line 2.")

# Read specific sections
content = fs.read_file_section("document.txt", start_line=1, end_line=1)
print(content)  # "Hello, World!"

# Modify sections safely
success = fs.modify_file_section("document.txt", 1, 1, "Hello, File Editor!")

# Search in files
results = fs.search_in_file("document.txt", "File Editor")
for line_num, line_content in results:
    print(f"Line {line_num}: {line_content}")
```

### Direct Core Usage

```python
from file_editor import MmapEditor, StreamEditor, MarkdownEditor

# Memory-mapped editing for random access
with MmapEditor("large_file.dat") as editor:
    data = editor.read_slice(1000, 2000)  # Read bytes 1000-2000
    editor.write_slice(500, b"new data")   # Write at offset 500
    pos = editor.find(b"pattern")          # Find pattern

# Streaming for sequential processing
editor = StreamEditor("huge_file.txt")
for chunk in editor.read_chunks():
    process(chunk)  # Process without loading entire file

# Markdown-specific operations
md_editor = MarkdownEditor("document.md")
md_editor.edit_section_streaming("Introduction", "New intro content")
md_editor.insert_section("New Section", "Content here", level=2)
```

## Core Concepts

### 1. Memory-Mapped Files (`MmapEditor`)

Best for random access patterns and files with frequent seeks:

```python
from file_editor import MmapEditor

with MmapEditor("data.bin", mode="r+b") as editor:
    # Direct byte-level access
    data = editor.read_slice(offset, length)
    editor.write_slice(offset, new_data)
    
    # Pattern operations
    positions = editor.find_all(b"search_pattern")
    editor.replace_all(b"old", b"new")  # Same length only
    
    # File operations
    editor.resize(new_size)
    editor.flush()
```

### 2. Streaming Operations (`StreamEditor`)

Best for sequential processing and memory-bounded operations:

```python
from file_editor import StreamEditor

editor = StreamEditor("large_file.txt")

# Process in chunks
for chunk in editor.read_chunks(binary=False):
    transformed = process_chunk(chunk)

# Process lines efficiently
def transform_line(line):
    return line.upper() if "important" in line else line

output_path = editor.process_lines(transform_line)

# Memory-efficient operations
line_count = editor.count_lines()
first_10 = editor.head(10)
last_10 = editor.tail(10)
```

### 3. Seek-Based Operations (`SeekEditor`)

Best for targeted access to specific file positions:

```python
from file_editor import SeekEditor, LineIndexedFile

# Direct seek operations
with SeekEditor("file.txt") as editor:
    data = editor.read_at(offset=100, size=50)
    editor.write_at(offset=200, data=b"new content")
    editor.insert_at(offset=150, data=b"inserted")

# Line-indexed access (O(1) line access)
indexed = LineIndexedFile("text_file.txt")
line_5 = indexed.get_line(4)  # 0-based indexing
lines_10_to_20 = indexed.get_lines(9, 20)
```

## Format-Specific Editors

### Markdown (`MarkdownEditor`)

```python
from file_editor import MarkdownEditor

editor = MarkdownEditor("document.md")

# Section operations
sections = editor.get_sections()
editor.edit_section_streaming("Section Title", "New content")
editor.insert_section("New Section", "Content", level=2, after_section="Introduction")
editor.remove_section("Old Section")

# Utility operations
toc = editor.get_table_of_contents()
editor.update_links({"old_url": "new_url"})
```

### CSV (`CSVEditor`)

```python
from file_editor import CSVEditor

editor = CSVEditor("data.csv")

# Basic operations
headers = editor.get_headers()
row_count = editor.count_rows()
stats = editor.get_column_stats("age")

# Data processing
filtered_path = editor.filter_rows(lambda row: int(row["age"]) > 25)
updated_path = editor.update_column("salary", lambda x: str(int(x) * 1.1))
new_path = editor.add_column("bonus", lambda row: str(int(row["salary"]) * 0.1))

# Sorting (loads into memory)
editor.sort_by_column("age", reverse=True)
```

### Text (`TextEditor`)

```python
from file_editor import TextEditor, FastTextEditor

editor = TextEditor("code.py")

# Line operations
editor.insert_lines(10, ["new line 1", "new line 2"])
editor.delete_lines(5, 7)  # Delete lines 5-7
editor.replace_lines(1, 3, ["replacement line 1", "replacement line 2"])

# Content operations
editor.replace_in_lines(r"old_function_name", "new_function_name")
editor.comment_lines(10, 15, "# ")
editor.indent_lines(5, 10, "    ")

# Analysis
matches = list(editor.find_lines(r"def \w+"))
stats = editor.word_count()
section = editor.extract_section(r"^class", r"^def")

# Fast text editor with line indexing
fast_editor = FastTextEditor("large_file.txt")
line_100 = fast_editor.get_line(100)
lines_50_to_100 = fast_editor.get_lines_range(50, 100)
```

## Safety and Production Features

### Atomic Operations and Rollback

All operations are atomic with automatic rollback on failure:

```python
from file_editor import safe_edit_context, ProductionFileEditor

# Manual safety context
with safe_edit_context("important_file.txt") as safe_op:
    temp_file = safe_op.get_temp_file()
    # Perform operations on temp_file
    safe_op.atomic_replace(temp_file)  # Atomic replacement

# Production editor with all safety features
editor = ProductionFileEditor()
success = editor.partial_replace("file.txt", start_offset=100, end_offset=200, new_content=b"data")
```

### Performance Monitoring

```python
from file_editor import performance_monitor

# Monitor operations
with performance_monitor.measure_operation("my_operation"):
    # Perform file operations
    pass

# Get statistics
stats = performance_monitor.get_stats("my_operation")
print(f"Average time: {stats['average_time']:.3f}s")
```

### Concurrent Access

Built-in file locking prevents race conditions:

```python
from file_editor import AgentFileSystem

# Multiple agents can safely access the same workspace
agent1 = AgentFileSystem("shared_workspace")
agent2 = AgentFileSystem("shared_workspace")

# Operations are automatically locked and coordinated
agent1.modify_file_section("shared.txt", 1, 5, "content from agent 1")
agent2.modify_file_section("shared.txt", 10, 15, "content from agent 2")
```

## Examples

See the `examples/` directory for comprehensive usage examples:

- `basic_usage.py` - Core functionality demonstrations
- `agent_integration.py` - AI agent integration patterns
- `performance_demo.py` - Performance optimization examples

Run examples:

```bash
uv run examples/basic_usage.py
uv run examples/agent_integration.py
```

## Testing

Run the test suite:

```bash
uv run pytest
```

For benchmarks:

```bash
uv run pytest --benchmark-only
```

## Performance Characteristics

- **Memory-mapped files**: Up to 100x faster for random access, O(1) seeks
- **Streaming**: Constant memory usage regardless of file size
- **Chunk processing**: Optimal chunk sizes 64KB-1MB depending on use case
- **Line indexing**: O(1) line access after initial O(n) indexing

## Architecture

```
file_editor/
├── core/           # Core editing engines
│   ├── mmap_editor.py     # Memory-mapped operations
│   ├── stream_editor.py   # Streaming operations
│   ├── seek_editor.py     # Seek-based operations
│   └── safety.py          # Safety mechanisms
├── formats/        # Format-specific editors
│   ├── markdown.py        # Markdown operations
│   ├── csv.py            # CSV operations
│   └── text.py           # Text operations
└── agent/          # Agent-friendly interface
    └── interface.py       # High-level abstractions
```

## Contributing

Contributions are welcome! Please see `CONTRIBUTING.md` for guidelines.

## License

This project is licensed under the MIT License - see the `LICENSE` file for details.

## Performance Tips

1. **Choose the right editor**: Memory-mapped for random access, streaming for sequential
2. **Optimize chunk sizes**: Start with 256KB, adjust based on your access patterns
3. **Use line indexing**: For frequent line-based access to the same file
4. **Batch operations**: Group related edits to minimize lock overhead
5. **Monitor performance**: Use the built-in performance monitoring to identify bottlenecks

## Troubleshooting

**Large file performance**: Use streaming editors and adjust chunk sizes
**Memory usage**: Prefer streaming over memory-mapped for sequential access
**Concurrent access**: Built-in locking handles this automatically
**File corruption**: All operations are atomic with automatic rollback

For more issues, check the GitHub issues page or consult the documentation.