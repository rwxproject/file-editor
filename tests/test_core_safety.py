"""Comprehensive tests for safety mechanisms."""
import tempfile
import threading
import time
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest
from file_editor.core.safety import (
    PerformanceMonitor,
    ProductionFileEditor,
    RetryableOperation,
    SafeFileOperation,
    performance_monitor,
    production_safe_edit,
    safe_edit_context,
)


class TestSafeFileOperation:
    """Test safe file operation context manager."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.txt"

    def teardown_method(self) -> None:
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_successful_operation(self) -> None:
        """Test successful file operation with backup and cleanup."""
        original_content = "Original content"
        self.test_file.write_text(original_content)

        with SafeFileOperation(self.test_file) as safe_op:
            # Backup should exist
            assert safe_op.backup_path.exists()
            backup_content = safe_op.backup_path.read_text()
            assert backup_content == original_content

            # Modify file
            temp_file = safe_op.get_temp_file()
            temp_file.write_text("Modified content")
            safe_op.atomic_replace(temp_file)

        # After successful operation, backup should be removed
        assert not safe_op.backup_path.exists()
        assert self.test_file.read_text() == "Modified content"

    def test_failed_operation_rollback(self) -> None:
        """Test rollback on failed operation."""
        original_content = "Original content"
        self.test_file.write_text(original_content)

        try:
            with SafeFileOperation(self.test_file) as safe_op:
                # Backup should exist
                assert safe_op.backup_path.exists()

                # Simulate a failure
                raise ValueError("Simulated error")
        except ValueError:
            pass  # Expected

        # After failed operation, original content should be restored
        assert self.test_file.read_text() == original_content
        assert not safe_op.backup_path.exists()

    def test_no_backup_option(self) -> None:
        """Test operation without creating backup."""
        original_content = "Original content"
        self.test_file.write_text(original_content)

        with SafeFileOperation(self.test_file, create_backup=False) as safe_op:
            # No backup should be created
            assert not safe_op.backup_path.exists()

            # Modify file
            temp_file = safe_op.get_temp_file()
            temp_file.write_text("Modified content")
            safe_op.atomic_replace(temp_file)

        assert self.test_file.read_text() == "Modified content"

    def test_nonexistent_file_operation(self) -> None:
        """Test operation on non-existent file."""
        nonexistent = Path(self.temp_dir) / "nonexistent.txt"

        with SafeFileOperation(nonexistent, create_backup=False) as safe_op:
            # Should work even if file doesn't exist initially
            temp_file = safe_op.get_temp_file()
            temp_file.write_text("New content")
            safe_op.atomic_replace(temp_file)

        assert nonexistent.read_text() == "New content"

    def test_concurrent_access_with_locks(self) -> None:
        """Test that file locking prevents concurrent modifications."""
        self.test_file.write_text("Original")
        results = []
        errors = []

        def modify_file(content: str, delay: float) -> None:
            try:
                with SafeFileOperation(self.test_file, timeout=5) as safe_op:
                    time.sleep(delay)  # Simulate work
                    temp_file = safe_op.get_temp_file()
                    temp_file.write_text(content)
                    safe_op.atomic_replace(temp_file)
                    results.append(content)
            except Exception as e:
                errors.append(e)

        # Start two concurrent operations
        thread1 = threading.Thread(target=modify_file, args=("Content1", 0.2))
        thread2 = threading.Thread(target=modify_file, args=("Content2", 0.1))

        thread1.start()
        thread2.start()

        thread1.join()
        thread2.join()

        # Both operations should complete (one after the other)
        assert len(results) == 2
        assert len(errors) == 0

        # Final content should be from one of the operations
        final_content = self.test_file.read_text()
        assert final_content in ["Content1", "Content2"]

    def test_lock_timeout(self) -> None:
        """Test lock timeout functionality."""
        self.test_file.write_text("Original")

        # Hold lock in one thread
        lock_acquired = threading.Event()
        operation_complete = threading.Event()

        def hold_lock() -> None:
            with SafeFileOperation(self.test_file, timeout=10):
                lock_acquired.set()
                operation_complete.wait(timeout=5)

        # Start lock holder
        holder_thread = threading.Thread(target=hold_lock)
        holder_thread.start()

        # Wait for lock to be acquired
        lock_acquired.wait(timeout=5)

        # Try to acquire lock with short timeout
        with pytest.raises(Exception):  # Should timeout
            with SafeFileOperation(self.test_file, timeout=1):
                pass

        # Release the lock
        operation_complete.set()
        holder_thread.join()

    def test_operation_log(self) -> None:
        """Test operation logging functionality."""
        self.test_file.write_text("Original")

        with SafeFileOperation(self.test_file) as safe_op:
            log = safe_op.get_operation_log()
            assert len(log) >= 1  # Should have backup creation logged

            temp_file = safe_op.get_temp_file()
            temp_file.write_text("Modified")
            safe_op.atomic_replace(temp_file)

            log = safe_op.get_operation_log()
            # Should have backup creation and atomic replace logged
            operations = [entry["operation"] for entry in log]
            assert "backup_created" in operations
            assert "atomic_replace" in operations


class TestSafeEditHelpers:
    """Test safe edit helper functions."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.txt"

    def teardown_method(self) -> None:
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_safe_edit_context(self) -> None:
        """Test safe_edit_context helper."""
        self.test_file.write_text("Original")

        with safe_edit_context(self.test_file) as safe_op:
            temp_file = safe_op.get_temp_file()
            temp_file.write_text("Modified")
            safe_op.atomic_replace(temp_file)

        assert self.test_file.read_text() == "Modified"

    def test_production_safe_edit(self) -> None:
        """Test production_safe_edit helper."""
        self.test_file.write_text("Line 1\nLine 2\nLine 3")

        def edit_function(input_file: Any, output_file: Any) -> None:
            for line in input_file:
                if "Line 2" in line:
                    output_file.write("Modified Line 2\n")
                else:
                    output_file.write(line)

        success = production_safe_edit(self.test_file, edit_function)
        assert success

        content = self.test_file.read_text()
        assert "Modified Line 2" in content
        assert "Line 1" in content
        assert "Line 3" in content

    def test_production_safe_edit_failure(self) -> None:
        """Test production_safe_edit with failing operation."""
        self.test_file.write_text("Original content")

        def failing_edit_function(input_file: Any, output_file: Any) -> None:
            raise ValueError("Simulated failure")

        success = production_safe_edit(self.test_file, failing_edit_function)
        assert not success

        # Original content should be preserved
        assert self.test_file.read_text() == "Original content"


class TestRetryableOperation:
    """Test retryable operation functionality."""

    def test_successful_operation_no_retry(self) -> None:
        """Test operation that succeeds on first try."""
        retry_op = RetryableOperation(max_retries=3)
        call_count = 0

        def successful_operation() -> str:
            nonlocal call_count
            call_count += 1
            return "success"

        result = retry_op.execute(successful_operation)
        assert result == "success"
        assert call_count == 1

    def test_operation_succeeds_after_retries(self) -> None:
        """Test operation that fails initially but succeeds after retries."""
        retry_op = RetryableOperation(max_retries=3, base_delay=0.01)
        call_count = 0

        def flaky_operation() -> str:
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Temporary failure")
            return "success"

        result = retry_op.execute(flaky_operation, retry_exceptions=(ConnectionError,))
        assert result == "success"
        assert call_count == 3

    def test_operation_fails_after_all_retries(self) -> None:
        """Test operation that fails even after all retries."""
        retry_op = RetryableOperation(max_retries=2, base_delay=0.01)
        call_count = 0

        def always_failing_operation() -> str:
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Persistent failure")

        with pytest.raises(ConnectionError, match="Persistent failure"):
            retry_op.execute(
                always_failing_operation, retry_exceptions=(ConnectionError,)
            )

        assert call_count == 3  # Initial + 2 retries

    def test_non_retryable_exception(self) -> None:
        """Test that non-retryable exceptions are not retried."""
        retry_op = RetryableOperation(max_retries=3)
        call_count = 0

        def operation_with_non_retryable_error() -> str:
            nonlocal call_count
            call_count += 1
            raise ValueError("Non-retryable error")

        with pytest.raises(ValueError, match="Non-retryable error"):
            retry_op.execute(
                operation_with_non_retryable_error, retry_exceptions=(ConnectionError,)
            )

        assert call_count == 1  # Should not retry

    def test_exponential_backoff(self) -> None:
        """Test exponential backoff delay calculation."""
        retry_op = RetryableOperation(max_retries=3, base_delay=0.1, max_delay=1.0)

        # Test internal delay calculation
        # This would require access to internal state or timing measurements
        # For now, we'll test that it doesn't crash with timing
        call_count = 0
        start_time = time.time()

        def slow_failing_operation() -> str:
            nonlocal call_count
            call_count += 1
            if call_count <= 2:
                raise ConnectionError("Failure")
            return "success"

        result = retry_op.execute(
            slow_failing_operation, retry_exceptions=(ConnectionError,)
        )
        end_time = time.time()

        assert result == "success"
        assert call_count == 3
        # Should have taken at least base_delay time due to retries
        assert end_time - start_time >= 0.1


class TestPerformanceMonitor:
    """Test performance monitoring functionality."""

    def test_measure_operation(self) -> None:
        """Test operation measurement."""
        monitor = PerformanceMonitor()

        with monitor.measure_operation("test_op"):
            time.sleep(0.1)  # Simulate work

        stats = monitor.get_stats("test_op")
        assert stats["count"] == 1
        assert stats["total_time"] >= 0.1
        assert stats["average_time"] >= 0.1
        assert stats["min_time"] >= 0.1
        assert stats["max_time"] >= 0.1

    def test_multiple_operations(self) -> None:
        """Test multiple operation measurements."""
        monitor = PerformanceMonitor()

        # Measure same operation multiple times
        for i in range(3):
            with monitor.measure_operation("test_op"):
                time.sleep(0.05 * (i + 1))  # Variable duration

        stats = monitor.get_stats("test_op")
        assert stats["count"] == 3
        assert stats["min_time"] < stats["max_time"]
        assert stats["average_time"] > stats["min_time"]

    def test_different_operations(self) -> None:
        """Test measuring different operations."""
        monitor = PerformanceMonitor()

        with monitor.measure_operation("op1"):
            time.sleep(0.05)

        with monitor.measure_operation("op2"):
            time.sleep(0.1)

        stats1 = monitor.get_stats("op1")
        stats2 = monitor.get_stats("op2")

        assert stats1["count"] == 1
        assert stats2["count"] == 1
        assert stats2["total_time"] > stats1["total_time"]

    def test_get_all_stats(self) -> None:
        """Test getting all statistics."""
        monitor = PerformanceMonitor()

        with monitor.measure_operation("op1"):
            time.sleep(0.01)

        with monitor.measure_operation("op2"):
            time.sleep(0.01)

        all_stats = monitor.get_all_stats()
        assert "op1" in all_stats
        assert "op2" in all_stats
        assert all_stats["op1"]["count"] == 1
        assert all_stats["op2"]["count"] == 1

    def test_nonexistent_operation_stats(self) -> None:
        """Test getting stats for non-existent operation."""
        monitor = PerformanceMonitor()
        stats = monitor.get_stats("nonexistent")
        assert stats == {}

    def test_global_performance_monitor(self) -> None:
        """Test global performance monitor instance."""
        with performance_monitor.measure_operation("global_test"):
            time.sleep(0.01)

        stats = performance_monitor.get_stats("global_test")
        assert stats["count"] == 1


class TestProductionFileEditor:
    """Test production file editor."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.bin"

    def teardown_method(self) -> None:
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_partial_replace_success(self) -> None:
        """Test successful partial replacement."""
        original_data = b"ABCDEFGHIJKLMNOPQRSTUVWXYZ"
        self.test_file.write_bytes(original_data)

        editor = ProductionFileEditor()
        success = editor.partial_replace(self.test_file, 5, 10, b"12345")

        assert success
        result = self.test_file.read_bytes()
        expected = b"ABCDE12345KLMNOPQRSTUVWXYZ"
        assert result == expected

    def test_partial_replace_failure_handling(self) -> None:
        """Test partial replacement failure handling."""
        nonexistent = Path(self.temp_dir) / "nonexistent.bin"

        editor = ProductionFileEditor()
        success = editor.partial_replace(nonexistent, 0, 5, b"test")

        assert not success
        assert not nonexistent.exists()

    def test_performance_monitoring_integration(self) -> None:
        """Test that operations are performance monitored."""
        original_data = b"Test data for monitoring"
        self.test_file.write_bytes(original_data)

        editor = ProductionFileEditor()

        # Clear any existing stats
        editor.monitor = PerformanceMonitor()

        success = editor.partial_replace(self.test_file, 0, 4, b"XXXX")
        assert success

        # Check that operation was monitored
        stats = editor.monitor.get_stats("partial_replace")
        assert stats["count"] == 1
        assert stats["total_time"] > 0


class TestConcurrencySafety:
    """Test concurrency safety mechanisms."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()
        self.test_file = Path(self.temp_dir) / "test.txt"

    def teardown_method(self) -> None:
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_multiple_readers_safe(self) -> None:
        """Test that multiple readers can access file safely."""
        self.test_file.write_text("Shared content")
        results = []
        errors = []

        def read_operation(reader_id: int) -> None:
            try:
                # Simulate reading with minimal locking
                content = self.test_file.read_text()
                results.append(f"Reader {reader_id}: {content.strip()}")
                time.sleep(0.1)  # Simulate processing
            except Exception as e:
                errors.append(e)

        # Start multiple readers
        threads = []
        for i in range(5):
            thread = threading.Thread(target=read_operation, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all to complete
        for thread in threads:
            thread.join()

        assert len(errors) == 0
        assert len(results) == 5
        for result in results:
            assert "Shared content" in result

    def test_write_operations_serialized(self) -> None:
        """Test that write operations are properly serialized."""
        self.test_file.write_text("Initial")
        successful_operations = []
        failed_operations = []

        def write_operation(writer_id: int, content: str) -> None:
            try:
                with safe_edit_context(self.test_file, timeout=5) as safe_op:
                    time.sleep(0.1)  # Simulate work
                    temp_file = safe_op.get_temp_file()
                    temp_file.write_text(f"Content from writer {writer_id}: {content}")
                    safe_op.atomic_replace(temp_file)
                    successful_operations.append(writer_id)
            except Exception as e:
                failed_operations.append((writer_id, e))

        # Start multiple writers
        threads = []
        for i in range(3):
            thread = threading.Thread(target=write_operation, args=(i, f"data_{i}"))
            threads.append(thread)
            thread.start()

        # Wait for all to complete
        for thread in threads:
            thread.join()

        # All operations should succeed (they should be serialized)
        assert len(successful_operations) == 3
        assert len(failed_operations) == 0

        # Final content should be from one of the writers
        final_content = self.test_file.read_text()
        assert "Content from writer" in final_content


class TestErrorScenarios:
    """Test various error scenarios and recovery."""

    def setup_method(self) -> None:
        """Set up test environment."""
        self.temp_dir = tempfile.mkdtemp()

    def teardown_method(self) -> None:
        """Clean up test environment."""
        import shutil

        shutil.rmtree(self.temp_dir)

    def test_disk_full_simulation(self) -> None:
        """Test handling when disk becomes full."""
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_text("Original content")

        # Mock os.replace to simulate disk full error
        with patch("os.replace", side_effect=OSError("No space left on device")):
            with pytest.raises(OSError):
                with SafeFileOperation(test_file) as safe_op:
                    temp_file = safe_op.get_temp_file()
                    temp_file.write_text("New content")
                    safe_op.atomic_replace(temp_file)

        # Original file should be restored
        assert test_file.read_text() == "Original content"

    def test_permission_denied_handling(self) -> None:
        """Test handling of permission denied errors."""
        test_file = Path(self.temp_dir) / "readonly.txt"
        test_file.write_text("Original content")
        test_file.chmod(0o444)  # Read-only

        try:
            with pytest.raises(PermissionError):
                with SafeFileOperation(test_file):
                    pass  # Should fail on lock acquisition
        finally:
            # Restore permissions for cleanup
            test_file.chmod(0o666)

    def test_interrupted_operation_cleanup(self) -> None:
        """Test cleanup when operation is interrupted."""
        test_file = Path(self.temp_dir) / "test.txt"
        test_file.write_text("Original content")

        # Simulate interruption during operation
        safe_op = SafeFileOperation(test_file)
        safe_op.__enter__()

        # Backup should exist
        assert safe_op.backup_path.exists()

        # Simulate exception without proper exit
        try:
            safe_op.__exit__(KeyboardInterrupt, KeyboardInterrupt(), None)
        except:
            pass

        # File should be restored
        assert test_file.read_text() == "Original content"
        assert not safe_op.backup_path.exists()

    @pytest.mark.integration
    def test_stress_test_concurrent_operations(self) -> None:
        """Stress test with many concurrent operations."""
        test_file = Path(self.temp_dir) / "stress_test.txt"
        test_file.write_text("Initial content")

        successful_ops = []
        failed_ops = []

        def stress_operation(op_id: int) -> None:
            try:
                with safe_edit_context(test_file, timeout=10) as safe_op:
                    # Random delay to increase contention
                    import random

                    time.sleep(random.uniform(0.01, 0.05))

                    temp_file = safe_op.get_temp_file()
                    temp_file.write_text(f"Operation {op_id} content")
                    safe_op.atomic_replace(temp_file)
                    successful_ops.append(op_id)
            except Exception as e:
                failed_ops.append((op_id, e))

        # Start many concurrent operations
        threads = []
        for i in range(20):
            thread = threading.Thread(target=stress_operation, args=(i,))
            threads.append(thread)
            thread.start()

        # Wait for all to complete
        for thread in threads:
            thread.join(timeout=30)  # Generous timeout

        # Most operations should succeed
        assert len(successful_ops) > 15  # Allow for some timeouts
        assert len(failed_ops) < 5

        # File should contain content from one of the operations
        final_content = test_file.read_text()
        assert "Operation" in final_content
        assert "content" in final_content
