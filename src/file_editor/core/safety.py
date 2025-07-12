"""Safety mechanisms for production-grade file editing."""
import logging
import os
import shutil
import tempfile
import time
from collections.abc import Callable
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Optional, Union

from filelock import FileLock

logger = logging.getLogger(__name__)


class SafeFileOperation:
    """Context manager for safe file operations with automatic rollback."""

    def __init__(
        self, file_path: Union[str, Path], timeout: int = 30, create_backup: bool = True
    ):
        """Initialize safe file operation.

        Args:
            file_path: Path to the file to operate on
            timeout: Lock timeout in seconds
            create_backup: Whether to create a backup before operations
        """
        self.file_path = Path(file_path)
        self.timeout = timeout
        self.create_backup = create_backup
        self.lock_path = Path(f"{self.file_path}.lock")
        self.backup_path = Path(f"{self.file_path}.backup.{int(time.time())}")
        self.temp_path: Optional[Path] = None
        self.lock: Optional[FileLock] = None
        self._operation_log = []

    def __enter__(self):
        """Enter context manager."""
        self.lock = FileLock(self.lock_path, timeout=self.timeout)

        try:
            self.lock.acquire()
            logger.info(f"Acquired lock for {self.file_path}")

            if self.create_backup and self.file_path.exists():
                shutil.copy2(self.file_path, self.backup_path)
                logger.info(f"Created backup: {self.backup_path}")
                self._log_operation("backup_created", str(self.backup_path))

            return self

        except Exception as e:
            logger.error(f"Failed to acquire lock for {self.file_path}: {e}")
            if self.lock:
                self.lock.release()
            raise

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Exit context manager."""
        try:
            if exc_type is not None:
                # Exception occurred - restore from backup
                logger.error(f"Operation failed: {exc_val}")
                self._restore_from_backup()
            else:
                # Success - clean up backup
                if self.backup_path.exists():
                    os.remove(self.backup_path)
                    logger.info("Operation successful, removed backup")
                    self._log_operation("backup_removed", "success")

        finally:
            # Clean up temp files
            if self.temp_path and self.temp_path.exists():
                os.remove(self.temp_path)

            # Release lock
            if self.lock:
                self.lock.release()
                logger.info(f"Released lock for {self.file_path}")

    def _restore_from_backup(self):
        """Restore file from backup."""
        if self.backup_path.exists():
            shutil.move(self.backup_path, self.file_path)
            logger.info(f"Restored from backup: {self.backup_path}")
            self._log_operation("restored_from_backup", str(self.backup_path))
        else:
            logger.warning("No backup file found for restoration")

    def _log_operation(self, operation: str, details: str):
        """Log operation for audit trail."""
        self._operation_log.append(
            {"timestamp": time.time(), "operation": operation, "details": details}
        )

    def get_temp_file(self) -> Path:
        """Get a temporary file in the same directory."""
        if self.temp_path is None:
            with tempfile.NamedTemporaryFile(
                dir=self.file_path.parent,
                prefix=f".{self.file_path.name}.",
                suffix=".tmp",
                delete=False,
            ) as tmp:
                self.temp_path = Path(tmp.name)

        return self.temp_path

    def atomic_replace(self, source: Union[str, Path]):
        """Atomically replace the target file with source."""
        source = Path(source)
        if not source.exists():
            raise FileNotFoundError(f"Source file not found: {source}")

        os.replace(source, self.file_path)
        logger.info(f"Atomically replaced {self.file_path} with {source}")
        self._log_operation("atomic_replace", f"{source} -> {self.file_path}")

    def get_operation_log(self) -> list[dict]:
        """Get operation log for debugging."""
        return self._operation_log.copy()


@contextmanager
def safe_edit_context(file_path: Union[str, Path], timeout: int = 30):
    """Context manager for safe file editing.

    Args:
        file_path: Path to file to edit
        timeout: Lock timeout in seconds

    Yields:
        SafeFileOperation instance
    """
    with SafeFileOperation(file_path, timeout) as safe_op:
        yield safe_op


def production_safe_edit(
    file_path: Union[str, Path],
    edit_function: Callable[[Any, Any], None],
    timeout: int = 30,
) -> bool:
    """Production-grade safe file editing.

    Args:
        file_path: Path to file to edit
        edit_function: Function that takes (input_file, output_file) and performs edit
        timeout: Lock timeout in seconds

    Returns:
        True if edit was successful, False otherwise
    """
    try:
        with safe_edit_context(file_path, timeout) as safe_op:
            temp_file = safe_op.get_temp_file()

            # Perform edit operation
            with open(file_path) as input_f, open(temp_file, "w") as output_f:
                edit_function(input_f, output_f)

            # Atomic replace
            safe_op.atomic_replace(temp_file)

        return True

    except Exception as e:
        logger.error(f"Safe edit failed for {file_path}: {e}")
        return False


class RetryableOperation:
    """Retryable operation with exponential backoff."""

    def __init__(
        self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0
    ):
        """Initialize retryable operation.

        Args:
            max_retries: Maximum number of retry attempts
            base_delay: Base delay between retries in seconds
            max_delay: Maximum delay between retries in seconds
        """
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay

    def execute(
        self, operation: Callable[[], Any], retry_exceptions: tuple = (Exception,)
    ) -> Any:
        """Execute operation with retry logic.

        Args:
            operation: Function to execute
            retry_exceptions: Tuple of exceptions that should trigger retry

        Returns:
            Result of operation

        Raises:
            Last exception if all retries failed
        """
        last_exception = None

        for attempt in range(self.max_retries + 1):
            try:
                return operation()

            except retry_exceptions as e:
                last_exception = e

                if attempt < self.max_retries:
                    delay = min(self.base_delay * (2**attempt), self.max_delay)
                    logger.warning(
                        f"Attempt {attempt + 1} failed: {e}. "
                        f"Retrying in {delay:.1f} seconds..."
                    )
                    time.sleep(delay)
                else:
                    logger.error(f"All {self.max_retries + 1} attempts failed")

        raise last_exception


class PerformanceMonitor:
    """Monitor file operation performance."""

    def __init__(self):
        self.metrics = {}

    @contextmanager
    def measure_operation(self, operation_name: str):
        """Context manager to measure operation duration.

        Args:
            operation_name: Name of operation being measured
        """
        start_time = time.perf_counter()
        try:
            yield
        finally:
            duration = time.perf_counter() - start_time
            self._record_metric(operation_name, duration)

    def _record_metric(self, operation: str, duration: float):
        """Record performance metric."""
        if operation not in self.metrics:
            self.metrics[operation] = {
                "count": 0,
                "total_time": 0.0,
                "min_time": float("inf"),
                "max_time": 0.0,
            }

        metrics = self.metrics[operation]
        metrics["count"] += 1
        metrics["total_time"] += duration
        metrics["min_time"] = min(metrics["min_time"], duration)
        metrics["max_time"] = max(metrics["max_time"], duration)

    def get_stats(self, operation: str) -> dict:
        """Get statistics for an operation.

        Args:
            operation: Operation name

        Returns:
            Dictionary with performance statistics
        """
        if operation not in self.metrics:
            return {}

        metrics = self.metrics[operation]
        avg_time = metrics["total_time"] / metrics["count"]

        return {
            "count": metrics["count"],
            "total_time": metrics["total_time"],
            "average_time": avg_time,
            "min_time": metrics["min_time"],
            "max_time": metrics["max_time"],
        }

    def get_all_stats(self) -> dict:
        """Get all recorded statistics."""
        return {op: self.get_stats(op) for op in self.metrics.keys()}


# Global performance monitor instance
performance_monitor = PerformanceMonitor()


class ProductionFileEditor:
    """Enterprise-grade partial file editing system."""

    def __init__(self, default_timeout: int = 30, default_chunk_size: int = 256 * 1024):
        """Initialize production file editor.

        Args:
            default_timeout: Default lock timeout
            default_chunk_size: Default chunk size for operations
        """
        self.timeout = default_timeout
        self.chunk_size = default_chunk_size
        self.logger = logging.getLogger(__name__)
        self.monitor = PerformanceMonitor()

    @contextmanager
    def safe_edit_context(self, file_path: Path):
        """Context manager ensuring safe file modifications."""
        with SafeFileOperation(file_path, self.timeout) as safe_op:
            yield safe_op

    def partial_replace(
        self,
        file_path: Union[str, Path],
        start_offset: int,
        end_offset: int,
        new_content: bytes,
    ) -> bool:
        """Replace specific byte range efficiently.

        Args:
            file_path: Path to file
            start_offset: Start offset
            end_offset: End offset
            new_content: New content to insert

        Returns:
            True if successful
        """
        file_path = Path(file_path)

        with self.monitor.measure_operation("partial_replace"):
            try:
                with self.safe_edit_context(file_path) as safe_op:
                    temp_file = safe_op.get_temp_file()

                    with open(file_path, "rb") as src, open(temp_file, "wb") as dst:
                        # Copy before section
                        if start_offset > 0:
                            src.seek(0)
                            dst.write(src.read(start_offset))

                        # Write new content
                        dst.write(new_content)

                        # Copy after section
                        src.seek(end_offset)
                        dst.write(src.read())

                    safe_op.atomic_replace(temp_file)

                return True

            except Exception as e:
                self.logger.error(f"Partial replace failed: {e}")
                return False
