"""CSV file editing with efficient chunk processing."""
import csv
import logging
from collections.abc import Callable, Iterator
from pathlib import Path
from typing import Any, Optional, Union

from ..core.safety import safe_edit_context
from ..core.stream_editor import StreamEditor

logger = logging.getLogger(__name__)

try:
    import pandas as pd

    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False
    pd = None


class CSVEditor(StreamEditor):
    """CSV file editor with efficient row-wise processing.

    Provides memory-efficient CSV editing capabilities for large files
    without loading entire datasets into memory.
    """

    def __init__(
        self,
        file_path: Union[str, Path],
        delimiter: str = ",",
        quotechar: str = '"',
        encoding: str = "utf-8",
    ):
        """Initialize CSV editor.

        Args:
            file_path: Path to CSV file
            delimiter: CSV delimiter character
            quotechar: Quote character for CSV
            encoding: File encoding
        """
        super().__init__(file_path)
        self.delimiter = delimiter
        self.quotechar = quotechar
        self.encoding = encoding
        self._headers: Optional[list[str]] = None

    def get_headers(self) -> list[str]:
        """Get CSV headers."""
        if self._headers is None:
            with open(self.file_path, encoding=self.encoding) as f:
                reader = csv.reader(
                    f, delimiter=self.delimiter, quotechar=self.quotechar
                )
                self._headers = next(reader, [])
        return self._headers

    def read_rows(self, skip_header: bool = True) -> Iterator[list[str]]:
        """Read CSV rows as lists.

        Args:
            skip_header: Whether to skip the header row

        Yields:
            List of values for each row
        """
        with open(self.file_path, encoding=self.encoding) as f:
            reader = csv.reader(f, delimiter=self.delimiter, quotechar=self.quotechar)

            if skip_header:
                next(reader, None)  # Skip header

            yield from reader

    def read_dict_rows(self) -> Iterator[dict[str, str]]:
        """Read CSV rows as dictionaries.

        Yields:
            Dictionary with column headers as keys
        """
        with open(self.file_path, encoding=self.encoding) as f:
            reader = csv.DictReader(
                f, delimiter=self.delimiter, quotechar=self.quotechar
            )
            yield from reader

    def process_rows(
        self,
        row_transformer: Callable[[dict[str, str]], Optional[dict[str, str]]],
        output_path: Optional[Union[str, Path]] = None,
    ) -> Optional[Path]:
        """Process CSV rows with a transformation function.

        Args:
            row_transformer: Function to transform each row (return None to skip)
            output_path: Output file path

        Returns:
            Path to output file
        """
        if output_path is None:
            output_path = self.file_path.with_suffix(".tmp")

        output_path = Path(output_path)
        headers = self.get_headers()

        try:
            with open(output_path, "w", newline="", encoding=self.encoding) as outfile:
                writer = csv.DictWriter(
                    outfile,
                    fieldnames=headers,
                    delimiter=self.delimiter,
                    quotechar=self.quotechar,
                )
                writer.writeheader()

                for row in self.read_dict_rows():
                    transformed_row = row_transformer(row)
                    if transformed_row is not None:
                        writer.writerow(transformed_row)

            return output_path

        except Exception as e:
            logger.error(f"Failed to process CSV rows: {e}")
            if output_path.exists():
                output_path.unlink()
            return None

    def filter_rows(
        self,
        predicate: Callable[[dict[str, str]], bool],
        output_path: Optional[Union[str, Path]] = None,
    ) -> Optional[Path]:
        """Filter CSV rows based on a predicate.

        Args:
            predicate: Function to test each row
            output_path: Output file path

        Returns:
            Path to filtered CSV file
        """
        return self.process_rows(
            lambda row: row if predicate(row) else None, output_path
        )

    def update_column(
        self,
        column_name: str,
        value_func: Callable[[str], str],
        output_path: Optional[Union[str, Path]] = None,
    ) -> Optional[Path]:
        """Update values in a specific column.

        Args:
            column_name: Name of column to update
            value_func: Function to transform column values
            output_path: Output file path

        Returns:
            Path to updated CSV file
        """

        def transform_row(row: dict[str, str]) -> dict[str, str]:
            if column_name in row:
                row[column_name] = value_func(row[column_name])
            return row

        return self.process_rows(transform_row, output_path)

    def add_column(
        self,
        column_name: str,
        value_func: Callable[[dict[str, str]], str],
        output_path: Optional[Union[str, Path]] = None,
    ) -> Optional[Path]:
        """Add a new column to the CSV.

        Args:
            column_name: Name of new column
            value_func: Function to compute column value from row data
            output_path: Output file path

        Returns:
            Path to updated CSV file
        """
        if output_path is None:
            output_path = self.file_path.with_suffix(".tmp")

        output_path = Path(output_path)
        headers = self.get_headers()
        new_headers = headers + [column_name]

        try:
            with open(output_path, "w", newline="", encoding=self.encoding) as outfile:
                writer = csv.DictWriter(
                    outfile,
                    fieldnames=new_headers,
                    delimiter=self.delimiter,
                    quotechar=self.quotechar,
                )
                writer.writeheader()

                for row in self.read_dict_rows():
                    row[column_name] = value_func(row)
                    writer.writerow(row)

            return output_path

        except Exception as e:
            logger.error(f"Failed to add CSV column: {e}")
            if output_path.exists():
                output_path.unlink()
            return None

    def sort_by_column(
        self,
        column_name: str,
        reverse: bool = False,
        key_func: Optional[Callable[[str], Any]] = None,
    ) -> bool:
        """Sort CSV by a specific column.

        Note: This loads all data into memory for sorting.

        Args:
            column_name: Column to sort by
            reverse: Sort in descending order
            key_func: Optional function to transform sort key

        Returns:
            True if sorting was successful
        """
        try:
            rows = list(self.read_dict_rows())
            headers = self.get_headers()

            if column_name not in headers:
                logger.error(f"Column '{column_name}' not found")
                return False

            # Sort rows
            sort_key = (
                lambda row: key_func(row[column_name]) if key_func else row[column_name]
            )
            rows.sort(key=sort_key, reverse=reverse)

            # Write sorted data
            with safe_edit_context(self.file_path) as safe_op:
                temp_file = safe_op.get_temp_file()

                with open(
                    temp_file, "w", newline="", encoding=self.encoding
                ) as outfile:
                    writer = csv.DictWriter(
                        outfile,
                        fieldnames=headers,
                        delimiter=self.delimiter,
                        quotechar=self.quotechar,
                    )
                    writer.writeheader()
                    writer.writerows(rows)

                safe_op.atomic_replace(temp_file)

            return True

        except Exception as e:
            logger.error(f"Failed to sort CSV: {e}")
            return False

    def count_rows(self) -> int:
        """Count number of data rows (excluding header)."""
        count = 0
        for _ in self.read_rows(skip_header=True):
            count += 1
        return count

    def get_column_stats(self, column_name: str) -> dict[str, Any]:
        """Get basic statistics for a column.

        Args:
            column_name: Column to analyze

        Returns:
            Dictionary with column statistics
        """
        values = []
        non_empty_values = []

        for row in self.read_dict_rows():
            value = row.get(column_name, "")
            values.append(value)
            if value.strip():
                non_empty_values.append(value)

        stats = {
            "total_rows": len(values),
            "non_empty_rows": len(non_empty_values),
            "empty_rows": len(values) - len(non_empty_values),
            "unique_values": len(set(non_empty_values)),
        }

        # Try to get numeric statistics
        try:
            numeric_values = [
                float(v)
                for v in non_empty_values
                if v.replace(".", "").replace("-", "").isdigit()
            ]
            if numeric_values:
                stats.update(
                    {
                        "numeric_count": len(numeric_values),
                        "min_value": min(numeric_values),
                        "max_value": max(numeric_values),
                        "avg_value": sum(numeric_values) / len(numeric_values),
                    }
                )
        except ValueError:
            pass

        return stats


if HAS_PANDAS:

    class PandasCSVEditor(CSVEditor):
        """CSV editor using pandas for advanced operations."""

        def __init__(
            self, file_path: Union[str, Path], chunk_size: int = 10000, **pandas_kwargs
        ):
            """Initialize pandas CSV editor.

            Args:
                file_path: Path to CSV file
                chunk_size: Chunk size for processing
                **pandas_kwargs: Additional arguments for pandas.read_csv
            """
            super().__init__(file_path)
            self.chunk_size = chunk_size
            self.pandas_kwargs = pandas_kwargs

        def process_chunks(
            self,
            chunk_processor: Callable[[pd.DataFrame], pd.DataFrame],
            output_path: Optional[Union[str, Path]] = None,
        ) -> Optional[Path]:
            """Process CSV in chunks using pandas.

            Args:
                chunk_processor: Function to process each DataFrame chunk
                output_path: Output file path

            Returns:
                Path to processed file
            """
            if output_path is None:
                output_path = self.file_path.with_suffix(".tmp")

            output_path = Path(output_path)

            try:
                first_chunk = True

                for chunk in pd.read_csv(
                    self.file_path, chunksize=self.chunk_size, **self.pandas_kwargs
                ):
                    processed_chunk = chunk_processor(chunk)

                    if processed_chunk is not None and not processed_chunk.empty:
                        mode = "w" if first_chunk else "a"
                        header = first_chunk

                        processed_chunk.to_csv(
                            output_path, mode=mode, header=header, index=False
                        )
                        first_chunk = False

                return output_path

            except Exception as e:
                logger.error(f"Failed to process CSV chunks with pandas: {e}")
                if output_path.exists():
                    output_path.unlink()
                return None

        def apply_operations(
            self,
            operations: list[Callable[[pd.DataFrame], pd.DataFrame]],
            output_path: Optional[Union[str, Path]] = None,
        ) -> Optional[Path]:
            """Apply multiple operations to CSV data.

            Args:
                operations: List of functions to apply to DataFrame chunks
                output_path: Output file path

            Returns:
                Path to processed file
            """

            def process_chunk(chunk: pd.DataFrame) -> pd.DataFrame:
                for operation in operations:
                    chunk = operation(chunk)
                return chunk

            return self.process_chunks(process_chunk, output_path)

else:
    # Provide a stub if pandas is not available
    class PandasCSVEditor(CSVEditor):
        def __init__(self, *args, **kwargs):
            raise ImportError(
                "pandas is required for PandasCSVEditor. Install with: uv add pandas"
            )
