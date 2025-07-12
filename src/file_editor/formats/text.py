"""Text file editing with line-based operations."""
import logging
import re
from collections.abc import Callable, Iterator
from pathlib import Path
from re import Pattern
from typing import Optional, Union

from ..core.safety import safe_edit_context
from ..core.seek_editor import LineIndexedFile
from ..core.stream_editor import ContextAwareStreamEditor

logger = logging.getLogger(__name__)


class TextEditor(ContextAwareStreamEditor):
    """Text file editor with advanced line-based operations.

    Provides efficient text editing capabilities including pattern matching,
    line operations, and context-aware transformations.
    """

    def __init__(self, file_path: Union[str, Path], encoding: str = "utf-8"):
        """Initialize text editor.

        Args:
            file_path: Path to text file
            encoding: File encoding
        """
        super().__init__(file_path)
        self.encoding = encoding

    def find_lines(
        self, pattern: Union[str, Pattern], case_sensitive: bool = True
    ) -> Iterator[tuple[int, str]]:
        """Find lines matching a pattern.

        Args:
            pattern: String or compiled regex pattern
            case_sensitive: Whether search is case sensitive

        Yields:
            Tuples of (line_number, line_content)
        """
        if isinstance(pattern, str):
            flags = 0 if case_sensitive else re.IGNORECASE
            pattern = re.compile(pattern, flags)

        for line_num, line in enumerate(self.read_lines(), 1):
            line_content = line.rstrip("\n")
            if pattern.search(line_content):
                yield (line_num, line_content)

    def replace_in_lines(
        self,
        search_pattern: Union[str, Pattern],
        replacement: str,
        max_replacements: Optional[int] = None,
    ) -> bool:
        """Replace pattern in lines throughout the file.

        Args:
            search_pattern: Pattern to search for
            replacement: Replacement string
            max_replacements: Maximum number of replacements (None for unlimited)

        Returns:
            True if any replacements were made
        """
        if isinstance(search_pattern, str):
            pattern = re.compile(re.escape(search_pattern))
        else:
            pattern = search_pattern

        replacements_made = 0

        def replace_line(line: str) -> str:
            nonlocal replacements_made

            if max_replacements is None or replacements_made < max_replacements:
                new_line, count = pattern.subn(replacement, line)
                replacements_made += count
                return new_line
            return line

        try:
            output_path = self.process_lines(replace_line)
            if replacements_made > 0 and output_path:
                with safe_edit_context(self.file_path) as safe_op:
                    safe_op.atomic_replace(output_path)
                logger.info(f"Made {replacements_made} replacements")
                return True

        except Exception as e:
            logger.error(f"Failed to replace text: {e}")

        return False

    def insert_lines(self, line_number: int, lines: list[str]) -> bool:
        """Insert lines at a specific position.

        Args:
            line_number: Line number to insert at (1-based)
            lines: Lines to insert

        Returns:
            True if insertion was successful
        """
        try:
            with safe_edit_context(self.file_path) as safe_op:
                temp_file = safe_op.get_temp_file()

                with open(self.file_path, encoding=self.encoding) as infile, open(
                    temp_file, "w", encoding=self.encoding
                ) as outfile:
                    current_line = 1

                    for line in infile:
                        if current_line == line_number:
                            # Insert new lines
                            for new_line in lines:
                                if not new_line.endswith("\n"):
                                    new_line += "\n"
                                outfile.write(new_line)

                        outfile.write(line)
                        current_line += 1

                    # Handle case where insertion is at end of file
                    if line_number > current_line:
                        for new_line in lines:
                            if not new_line.endswith("\n"):
                                new_line += "\n"
                            outfile.write(new_line)

                safe_op.atomic_replace(temp_file)
                return True

        except Exception as e:
            logger.error(f"Failed to insert lines: {e}")
            return False

    def delete_lines(self, start_line: int, end_line: Optional[int] = None) -> bool:
        """Delete lines from the file.

        Args:
            start_line: First line to delete (1-based)
            end_line: Last line to delete (inclusive, None for just start_line)

        Returns:
            True if deletion was successful
        """
        if end_line is None:
            end_line = start_line

        try:
            with safe_edit_context(self.file_path) as safe_op:
                temp_file = safe_op.get_temp_file()

                with open(self.file_path, encoding=self.encoding) as infile, open(
                    temp_file, "w", encoding=self.encoding
                ) as outfile:
                    current_line = 1

                    for line in infile:
                        if not (start_line <= current_line <= end_line):
                            outfile.write(line)
                        current_line += 1

                safe_op.atomic_replace(temp_file)
                return True

        except Exception as e:
            logger.error(f"Failed to delete lines: {e}")
            return False

    def replace_lines(
        self, start_line: int, end_line: int, new_lines: list[str]
    ) -> bool:
        """Replace a range of lines with new content.

        Args:
            start_line: First line to replace (1-based)
            end_line: Last line to replace (inclusive)
            new_lines: New lines to insert

        Returns:
            True if replacement was successful
        """
        try:
            with safe_edit_context(self.file_path) as safe_op:
                temp_file = safe_op.get_temp_file()

                with open(self.file_path, encoding=self.encoding) as infile, open(
                    temp_file, "w", encoding=self.encoding
                ) as outfile:
                    current_line = 1

                    for line in infile:
                        if current_line == start_line:
                            # Write replacement lines
                            for new_line in new_lines:
                                if not new_line.endswith("\n"):
                                    new_line += "\n"
                                outfile.write(new_line)

                        if not (start_line <= current_line <= end_line):
                            outfile.write(line)

                        current_line += 1

                safe_op.atomic_replace(temp_file)
                return True

        except Exception as e:
            logger.error(f"Failed to replace lines: {e}")
            return False

    def comment_lines(
        self, start_line: int, end_line: int, comment_prefix: str = "# "
    ) -> bool:
        """Comment out lines by adding a prefix.

        Args:
            start_line: First line to comment (1-based)
            end_line: Last line to comment (inclusive)
            comment_prefix: Comment prefix to add

        Returns:
            True if commenting was successful
        """

        def process_line(line: str, line_num: int) -> str:
            if start_line <= line_num <= end_line:
                return comment_prefix + line
            return line

        return self._process_lines_with_numbers(process_line)

    def uncomment_lines(
        self, start_line: int, end_line: int, comment_prefix: str = "# "
    ) -> bool:
        """Remove comment prefix from lines.

        Args:
            start_line: First line to uncomment (1-based)
            end_line: Last line to uncomment (inclusive)
            comment_prefix: Comment prefix to remove

        Returns:
            True if uncommenting was successful
        """

        def process_line(line: str, line_num: int) -> str:
            if start_line <= line_num <= end_line and line.startswith(comment_prefix):
                return line[len(comment_prefix) :]
            return line

        return self._process_lines_with_numbers(process_line)

    def _process_lines_with_numbers(self, processor: Callable[[str, int], str]) -> bool:
        """Process lines with line numbers."""
        try:
            with safe_edit_context(self.file_path) as safe_op:
                temp_file = safe_op.get_temp_file()

                with open(self.file_path, encoding=self.encoding) as infile, open(
                    temp_file, "w", encoding=self.encoding
                ) as outfile:
                    for line_num, line in enumerate(infile, 1):
                        processed_line = processor(line, line_num)
                        outfile.write(processed_line)

                safe_op.atomic_replace(temp_file)
                return True

        except Exception as e:
            logger.error(f"Failed to process lines: {e}")
            return False

    def indent_lines(
        self, start_line: int, end_line: int, indent: str = "    "
    ) -> bool:
        """Add indentation to lines.

        Args:
            start_line: First line to indent (1-based)
            end_line: Last line to indent (inclusive)
            indent: Indentation string to add

        Returns:
            True if indentation was successful
        """

        def process_line(line: str, line_num: int) -> str:
            if start_line <= line_num <= end_line and line.strip():
                return indent + line
            return line

        return self._process_lines_with_numbers(process_line)

    def dedent_lines(
        self, start_line: int, end_line: int, dedent_amount: int = 4
    ) -> bool:
        """Remove indentation from lines.

        Args:
            start_line: First line to dedent (1-based)
            end_line: Last line to dedent (inclusive)
            dedent_amount: Number of spaces to remove

        Returns:
            True if dedentation was successful
        """

        def process_line(line: str, line_num: int) -> str:
            if start_line <= line_num <= end_line:
                # Remove up to dedent_amount leading spaces
                spaces_to_remove = 0
                for char in line:
                    if char == " " and spaces_to_remove < dedent_amount:
                        spaces_to_remove += 1
                    else:
                        break
                return line[spaces_to_remove:]
            return line

        return self._process_lines_with_numbers(process_line)

    def extract_section(
        self,
        start_pattern: Union[str, Pattern],
        end_pattern: Union[str, Pattern],
        include_markers: bool = False,
    ) -> list[str]:
        """Extract section between two patterns.

        Args:
            start_pattern: Pattern marking start of section
            end_pattern: Pattern marking end of section
            include_markers: Whether to include the marker lines

        Returns:
            List of lines in the section
        """
        if isinstance(start_pattern, str):
            start_pattern = re.compile(start_pattern)
        if isinstance(end_pattern, str):
            end_pattern = re.compile(end_pattern)

        section_lines = []
        in_section = False

        for line in self.read_lines():
            line_content = line.rstrip("\n")

            if not in_section and start_pattern.search(line_content):
                in_section = True
                if include_markers:
                    section_lines.append(line_content)
                continue

            if in_section and end_pattern.search(line_content):
                if include_markers:
                    section_lines.append(line_content)
                break

            if in_section:
                section_lines.append(line_content)

        return section_lines

    def word_count(self) -> dict[str, int]:
        """Get word count statistics for the file.

        Returns:
            Dictionary with character, word, and line counts
        """
        char_count = 0
        word_count = 0
        line_count = 0

        for line in self.read_lines():
            line_count += 1
            char_count += len(line)
            words = line.split()
            word_count += len(words)

        return {"characters": char_count, "words": word_count, "lines": line_count}


class FastTextEditor(TextEditor):
    """Text editor optimized for common operations using line indexing."""

    def __init__(self, file_path: Union[str, Path], encoding: str = "utf-8"):
        """Initialize fast text editor with line indexing.

        Args:
            file_path: Path to text file
            encoding: File encoding
        """
        super().__init__(file_path, encoding)
        self._indexed_file: Optional[LineIndexedFile] = None

    def _get_indexed_file(self) -> LineIndexedFile:
        """Get or create line-indexed file."""
        if self._indexed_file is None:
            self._indexed_file = LineIndexedFile(self.file_path)
        return self._indexed_file

    def get_line(self, line_number: int) -> str:
        """Get a specific line efficiently.

        Args:
            line_number: Line number (1-based)

        Returns:
            Line content
        """
        indexed_file = self._get_indexed_file()
        return indexed_file.get_line(line_number - 1)  # Convert to 0-based

    def get_lines_range(self, start_line: int, end_line: int) -> list[str]:
        """Get a range of lines efficiently.

        Args:
            start_line: Starting line number (1-based, inclusive)
            end_line: Ending line number (1-based, inclusive)

        Returns:
            List of lines
        """
        indexed_file = self._get_indexed_file()
        return indexed_file.get_lines(start_line - 1, end_line)  # Convert to 0-based

    def replace_line_fast(self, line_number: int, new_content: str) -> bool:
        """Replace a single line efficiently.

        Args:
            line_number: Line number to replace (1-based)
            new_content: New line content

        Returns:
            True if replacement was successful
        """
        try:
            indexed_file = self._get_indexed_file()
            indexed_file.replace_line(
                line_number - 1, new_content
            )  # Convert to 0-based
            # Invalidate cached index since file changed
            self._indexed_file = None
            return True

        except Exception as e:
            logger.error(f"Failed to replace line: {e}")
            return False
