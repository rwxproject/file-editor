"""Agent-friendly file system interface for AI agents."""
import logging
import time
from pathlib import Path
from typing import Any, Optional

from ..core.safety import performance_monitor, safe_edit_context
from ..core.seek_editor import LineIndexedFile
from ..formats.csv import CSVEditor
from ..formats.markdown import MarkdownEditor
from ..formats.text import FastTextEditor, TextEditor

logger = logging.getLogger(__name__)


class AgentFileSystem:
    """File system abstraction for AI agents.

    Provides high-level, safe abstractions that hide complexity while
    maintaining efficiency. Agents should never directly manipulate
    file handles or deal with locking mechanisms.
    """

    def __init__(
        self,
        workspace_dir: str,
        chunk_size: int = 4096,
        max_file_size: int = 100 * 1024 * 1024,
    ):  # 100MB default
        """Initialize agent file system.

        Args:
            workspace_dir: Root directory for file operations
            chunk_size: Default chunk size for operations
            max_file_size: Maximum file size to process (safety limit)
        """
        self.workspace = Path(workspace_dir).resolve()
        self.chunk_size = chunk_size
        self.max_file_size = max_file_size
        self.operation_log = []

        # Ensure workspace exists
        self.workspace.mkdir(parents=True, exist_ok=True)

    def _validate_path(self, file_path: str) -> Path:
        """Validate and resolve file path within workspace.

        Args:
            file_path: Relative path from workspace

        Returns:
            Absolute path within workspace

        Raises:
            ValueError: If path is outside workspace or invalid
        """
        # Check for obvious malicious patterns
        if file_path.startswith("/") or "\\" in file_path or ":" in file_path:
            raise ValueError(f"Path '{file_path}' is outside workspace")

        full_path = (self.workspace / file_path).resolve()
        workspace_resolved = self.workspace.resolve()

        # Ensure path is within workspace
        try:
            full_path.relative_to(workspace_resolved)
        except ValueError:
            raise ValueError(f"Path '{file_path}' is outside workspace")

        return full_path

    def _check_file_size(self, file_path: Path):
        """Check if file size is within limits."""
        if file_path.exists():
            size = file_path.stat().st_size
            if size > self.max_file_size:
                raise ValueError(
                    f"File {file_path} ({size} bytes) exceeds maximum size ({self.max_file_size} bytes)"
                )

    def _log_operation(self, op_type: str, file_path: str, details: Any):
        """Maintain audit trail for agent operations."""
        self.operation_log.append(
            {
                "timestamp": time.time(),
                "operation": op_type,
                "file": file_path,
                "details": details,
            }
        )

    def file_exists(self, file_path: str) -> bool:
        """Check if file exists.

        Args:
            file_path: Relative path from workspace

        Returns:
            True if file exists
        """
        try:
            full_path = self._validate_path(file_path)
            return full_path.exists() and full_path.is_file()
        except ValueError:
            return False

    def get_file_info(self, file_path: str) -> Optional[dict[str, Any]]:
        """Get file information.

        Args:
            file_path: Relative path from workspace

        Returns:
            Dictionary with file info or None if file doesn't exist
        """
        try:
            full_path = self._validate_path(file_path)
            if not full_path.exists():
                return None

            stat = full_path.stat()
            return {
                "size": stat.st_size,
                "modified": stat.st_mtime,
                "created": stat.st_ctime,
                "is_text": self._is_text_file(full_path),
                "file_type": self._detect_file_type(full_path),
            }

        except Exception as e:
            logger.error(f"Failed to get file info for {file_path}: {e}")
            return None

    def _is_text_file(self, file_path: Path) -> bool:
        """Check if file is text-based."""
        try:
            with open(file_path, "rb") as f:
                chunk = f.read(8192)
                # Simple heuristic: if no null bytes in first chunk, likely text
                return b"\x00" not in chunk
        except Exception:
            return False

    def _detect_file_type(self, file_path: Path) -> str:
        """Detect file type based on extension."""
        suffix = file_path.suffix.lower()

        type_map = {
            ".md": "markdown",
            ".markdown": "markdown",
            ".txt": "text",
            ".csv": "csv",
            ".tsv": "csv",
            ".py": "python",
            ".js": "javascript",
            ".json": "json",
            ".xml": "xml",
            ".html": "html",
            ".yaml": "yaml",
            ".yml": "yaml",
        }

        return type_map.get(suffix, "unknown")

    def read_file_section(
        self, file_path: str, start_line: int, end_line: int
    ) -> Optional[str]:
        """Read specific section of file with automatic safety measures.

        Args:
            file_path: Relative path from workspace
            start_line: Starting line number (1-based)
            end_line: Ending line number (1-based, inclusive)

        Returns:
            File section content or None if failed
        """
        try:
            full_path = self._validate_path(file_path)
            self._check_file_size(full_path)

            with performance_monitor.measure_operation("read_section"):
                if self._is_text_file(full_path):
                    indexed_file = LineIndexedFile(full_path)
                    lines = indexed_file.get_lines(start_line - 1, end_line)
                    content = "\n".join(lines)
                else:
                    # For binary files, read byte ranges (approximate)
                    with open(full_path, "rb") as f:
                        # Simple approximation: 80 chars per line
                        start_byte = max(0, (start_line - 1) * 80)
                        end_byte = end_line * 80
                        f.seek(start_byte)
                        data = f.read(end_byte - start_byte)
                        content = data.decode("utf-8", errors="replace")

            self._log_operation("read", file_path, (start_line, end_line))
            return content

        except Exception as e:
            logger.error(f"Failed to read section from {file_path}: {e}")
            self._log_operation("failed_read", file_path, str(e))
            return None

    def read_full_file(
        self, file_path: str, max_lines: Optional[int] = None
    ) -> Optional[str]:
        """Read entire file with safety limits.

        Args:
            file_path: Relative path from workspace
            max_lines: Maximum number of lines to read

        Returns:
            File content or None if failed
        """
        try:
            full_path = self._validate_path(file_path)
            self._check_file_size(full_path)

            with performance_monitor.measure_operation("read_full"):
                if self._is_text_file(full_path):
                    with open(full_path, encoding="utf-8", errors="replace") as f:
                        if max_lines:
                            lines = []
                            for i, line in enumerate(f):
                                if i >= max_lines:
                                    break
                                lines.append(line.rstrip("\n"))
                            content = "\n".join(lines)
                        else:
                            content = f.read()
                else:
                    with open(full_path, "rb") as f:
                        data = f.read()
                        content = data.decode("utf-8", errors="replace")

            self._log_operation("read_full", file_path, max_lines)
            return content

        except Exception as e:
            logger.error(f"Failed to read file {file_path}: {e}")
            self._log_operation("failed_read_full", file_path, str(e))
            return None

    def modify_file_section(
        self, file_path: str, start_line: int, end_line: int, new_content: str
    ) -> bool:
        """Safely modify file section with automatic rollback.

        Args:
            file_path: Relative path from workspace
            start_line: Starting line number (1-based)
            end_line: Ending line number (1-based, inclusive)
            new_content: New content for the section

        Returns:
            True if modification was successful
        """
        try:
            full_path = self._validate_path(file_path)
            self._check_file_size(full_path)

            with performance_monitor.measure_operation("modify_section"):
                # Determine best editor based on file type
                file_type = self._detect_file_type(full_path)

                if file_type == "text":
                    editor = FastTextEditor(full_path)

                    # Convert new_content to list of lines
                    new_lines = new_content.split("\n")
                    success = editor.replace_lines(start_line, end_line, new_lines)

                else:
                    # Fallback to generic text editor
                    editor = TextEditor(full_path)
                    new_lines = new_content.split("\n")
                    success = editor.replace_lines(start_line, end_line, new_lines)

            if success:
                self._log_operation(
                    "modify", file_path, (start_line, end_line, len(new_content))
                )
            else:
                self._log_operation(
                    "failed_modify", file_path, f"Lines {start_line}-{end_line}"
                )

            return success

        except Exception as e:
            logger.error(f"Failed to modify section in {file_path}: {e}")
            self._log_operation("failed_modify", file_path, str(e))
            return False

    def append_to_file(self, file_path: str, content: str) -> bool:
        """Append content to end of file.

        Args:
            file_path: Relative path from workspace
            content: Content to append

        Returns:
            True if append was successful
        """
        try:
            full_path = self._validate_path(file_path)

            with safe_edit_context(full_path, timeout=5) as safe_op:
                # Create file if it doesn't exist
                if not full_path.exists():
                    full_path.touch()

                with open(full_path, "a", encoding="utf-8") as f:
                    if not content.endswith("\n"):
                        content += "\n"
                    f.write(content)

            self._log_operation("append", file_path, len(content))
            return True

        except Exception as e:
            logger.error(f"Failed to append to {file_path}: {e}")
            self._log_operation("failed_append", file_path, str(e))
            return False

    def create_file(self, file_path: str, content: str = "") -> bool:
        """Create a new file with optional initial content.

        Args:
            file_path: Relative path from workspace
            content: Initial file content

        Returns:
            True if file was created successfully
        """
        try:
            full_path = self._validate_path(file_path)

            if full_path.exists():
                logger.warning(f"File {file_path} already exists")
                return False

            # Create parent directories if needed
            full_path.parent.mkdir(parents=True, exist_ok=True)

            with open(full_path, "w", encoding="utf-8") as f:
                f.write(content)

            self._log_operation("create", file_path, len(content))
            return True

        except Exception as e:
            logger.error(f"Failed to create file {file_path}: {e}")
            self._log_operation("failed_create", file_path, str(e))
            return False

    def delete_file(self, file_path: str) -> bool:
        """Delete a file.

        Args:
            file_path: Relative path from workspace

        Returns:
            True if file was deleted successfully
        """
        try:
            full_path = self._validate_path(file_path)

            if not full_path.exists():
                logger.warning(f"File {file_path} does not exist")
                return False

            full_path.unlink()
            self._log_operation("delete", file_path, "success")
            return True

        except Exception as e:
            logger.error(f"Failed to delete file {file_path}: {e}")
            self._log_operation("failed_delete", file_path, str(e))
            return False

    def search_in_file(
        self,
        file_path: str,
        pattern: str,
        case_sensitive: bool = True,
        max_results: int = 100,
    ) -> list[tuple[int, str]]:
        """Search for pattern in file.

        Args:
            file_path: Relative path from workspace
            pattern: Search pattern
            case_sensitive: Whether search is case sensitive
            max_results: Maximum number of results to return

        Returns:
            List of (line_number, line_content) tuples
        """
        try:
            full_path = self._validate_path(file_path)
            self._check_file_size(full_path)

            editor = TextEditor(full_path)
            results = []

            for line_num, line_content in editor.find_lines(pattern, case_sensitive):
                results.append((line_num, line_content))
                if len(results) >= max_results:
                    break

            self._log_operation(
                "search", file_path, f"'{pattern}' -> {len(results)} results"
            )
            return results

        except Exception as e:
            logger.error(f"Failed to search in {file_path}: {e}")
            self._log_operation("failed_search", file_path, str(e))
            return []

    def get_file_stats(self, file_path: str) -> Optional[dict[str, int]]:
        """Get statistics about a text file.

        Args:
            file_path: Relative path from workspace

        Returns:
            Dictionary with file statistics or None if failed
        """
        try:
            full_path = self._validate_path(file_path)

            if not self._is_text_file(full_path):
                return None

            editor = TextEditor(full_path)
            stats = editor.word_count()

            self._log_operation("stats", file_path, stats)
            return stats

        except Exception as e:
            logger.error(f"Failed to get stats for {file_path}: {e}")
            self._log_operation("failed_stats", file_path, str(e))
            return None

    def list_files(self, directory: str = "", pattern: str = "*") -> list[str]:
        """List files in directory matching pattern.

        Args:
            directory: Subdirectory within workspace
            pattern: Glob pattern for file matching

        Returns:
            List of relative file paths
        """
        try:
            if directory:
                full_path = self._validate_path(directory)
            else:
                full_path = self.workspace

            if not full_path.is_dir():
                return []

            files = []
            # Use rglob to recursively search for files when at workspace root
            if full_path == self.workspace:
                glob_method = full_path.rglob
            else:
                glob_method = full_path.glob

            for path in glob_method(pattern):
                if path.is_file():
                    # Return relative path from the search directory
                    if directory:
                        rel_path = path.relative_to(full_path)
                    else:
                        rel_path = path.relative_to(self.workspace)
                    files.append(str(rel_path))

            return sorted(files)

        except Exception as e:
            logger.error(f"Failed to list files in {directory}: {e}")
            return []

    def get_operation_log(self) -> list[dict[str, Any]]:
        """Get operation log for debugging and audit purposes.

        Returns:
            List of operation log entries
        """
        return self.operation_log.copy()

    def clear_operation_log(self):
        """Clear the operation log."""
        self.operation_log.clear()


class SpecializedAgentEditors:
    """Specialized editors for specific file types with agent-friendly interfaces."""

    def __init__(self, agent_fs: AgentFileSystem):
        """Initialize with agent file system.

        Args:
            agent_fs: AgentFileSystem instance
        """
        self.agent_fs = agent_fs

    def markdown_edit_section(
        self, file_path: str, section_title: str, new_content: str
    ) -> bool:
        """Edit a markdown section by title.

        Args:
            file_path: Relative path to markdown file
            section_title: Title of section to edit
            new_content: New section content

        Returns:
            True if edit was successful
        """
        try:
            full_path = self.agent_fs._validate_path(file_path)
            editor = MarkdownEditor(full_path)
            success = editor.edit_section_streaming(section_title, new_content)

            if success:
                self.agent_fs._log_operation(
                    "markdown_edit_section", file_path, section_title
                )
            else:
                self.agent_fs._log_operation(
                    "failed_markdown_edit_section", file_path, section_title
                )

            return success

        except Exception as e:
            logger.error(f"Failed to edit markdown section: {e}")
            return False

    def csv_filter_rows(
        self, file_path: str, column: str, value: str, output_path: Optional[str] = None
    ) -> Optional[str]:
        """Filter CSV rows by column value.

        Args:
            file_path: Relative path to CSV file
            column: Column name to filter on
            value: Value to filter for
            output_path: Output file path (None for temporary)

        Returns:
            Path to filtered file or None if failed
        """
        try:
            full_path = self.agent_fs._validate_path(file_path)
            editor = CSVEditor(full_path)

            if output_path:
                output_full_path = self.agent_fs._validate_path(output_path)
            else:
                output_full_path = None

            result_path = editor.filter_rows(
                lambda row: row.get(column, "") == value, output_full_path
            )

            if result_path:
                # Return relative path
                rel_path = result_path.relative_to(self.agent_fs.workspace)
                self.agent_fs._log_operation(
                    "csv_filter", file_path, f"{column}={value}"
                )
                return str(rel_path)

        except Exception as e:
            logger.error(f"Failed to filter CSV: {e}")

        return None
