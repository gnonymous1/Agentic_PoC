import unittest
from unittest.mock import MagicMock, patch
import time
from datetime import datetime, timedelta
from cortex.observability import (
    ObservabilityEngine, LogLevel, Status, EventType, EventBus, TraceContext, Alert,
    record_metric, start_trace, end_trace, log, get_metrics, get_trace, query_logs, check_alerts, get_performance_stats
)

class TestObservabilityEngine(unittest.TestCase):
    def setUp(self):
        # Reset the singleton EventBus for each test to avoid side effects
        EventBus._instance = None
        self.mock_event_bus = MagicMock()

        # Patch EventBus.get_sync to return our mock
        with patch('cortex.events.EventBus.get_sync', return_value=self.mock_event_bus):
            self.engine = ObservabilityEngine()

    def test_record_metric(self):
        """Test recording metrics and aggregation logic."""
        self.engine.record_metric("test_metric", 10.0, {"tag": "v1"})
        self.engine.record_metric("test_metric", 20.0, {"tag": "v2"})
        self.engine.record_metric("test_metric", 30.0, {"tag": "v3"})

        # Verify metrics storage
        metrics = self.engine.metrics["test_metric"]
        self.assertEqual(len(metrics), 3)
        self.assertEqual(metrics[0]["value"], 10.0)
        self.assertEqual(metrics[2]["value"], 30.0)

        # Verify aggregation
        agg = self.engine.metric_aggregates["test_metric"]
        self.assertEqual(agg["count"], 3)
        self.assertEqual(agg["sum"], 60.0)
        self.assertEqual(agg["min"], 10.0)
        self.assertEqual(agg["max"], 30.0)
        self.assertEqual(agg["avg"], 20.0)

    def test_get_metrics(self):
        """Test retrieving metrics with filtering."""
        current_time = time.time()

        self.engine.metrics["old_metric"] = [{
            "name": "old_metric",
            "value": 5.0,
            "timestamp": current_time - 100,
            "tags": {}
        }]
        # Initialize aggregates
        self.engine.metric_aggregates["old_metric"] = {}

        self.engine.metrics["new_metric"] = [{
            "name": "new_metric",
            "value": 10.0,
            "timestamp": current_time,
            "tags": {}
        }]
        # Initialize aggregates
        self.engine.metric_aggregates["new_metric"] = {}

        # Get all metrics
        all_metrics = self.engine.get_metrics()
        self.assertIn("old_metric", all_metrics["metrics"])
        self.assertIn("new_metric", all_metrics["metrics"])

        # Get specific metric
        specific = self.engine.get_metrics("new_metric")
        self.assertEqual(specific["name"], "new_metric")
        self.assertEqual(specific["data_points"], 1)

        # Get non-existent metric
        missing = self.engine.get_metrics("missing_metric")
        self.assertEqual(missing["error"], "Metric not found")

        # Test window filtering
        with patch('time.time', return_value=current_time):
             res = self.engine.get_metrics("old_metric", window=50)
             self.assertEqual(res["data_points"], 0)

             res2 = self.engine.get_metrics("new_metric", window=50)
             self.assertEqual(res2["data_points"], 1)

    def test_trace_lifecycle(self):
        """Test start and end of traces."""
        # Start Trace
        trace_context = self.engine.start_trace("test_op", {"user": "admin"})
        self.assertIsInstance(trace_context, TraceContext)
        self.assertEqual(trace_context.operation, "test_op")
        self.assertEqual(trace_context.status, Status.PENDING)
        self.assertIn(trace_context.trace_id, self.engine.active_traces)

        # End Trace
        # Mock time to advance 2.5s
        start_time = trace_context.start_time
        with patch('time.time', return_value=start_time + 2.5):
            self.engine.end_trace(trace_context, Status.SUCCESS)

        self.assertEqual(trace_context.status, Status.SUCCESS)
        self.assertAlmostEqual(trace_context.end_time - trace_context.start_time, 2.5, delta=0.1)
        self.assertNotIn(trace_context.trace_id, self.engine.active_traces)
        self.assertIn(trace_context, self.engine.completed_traces)

        # Verify Metrics were recorded for trace
        duration_metrics = self.engine.metrics[f"trace.test_op.duration"]
        self.assertEqual(len(duration_metrics), 1)
        self.assertAlmostEqual(duration_metrics[0]["value"], 2.5, delta=0.1)

    def test_get_trace(self):
        """Test retrieving trace details."""
        # Active trace
        active_ctx = self.engine.start_trace("active_op")

        with patch('time.time', return_value=active_ctx.start_time + 1.0):
            trace_details = self.engine.get_trace(active_ctx.trace_id)
            self.assertEqual(trace_details["operation"], "active_op")
            self.assertEqual(trace_details["status"], "pending")
            self.assertAlmostEqual(trace_details["duration"], 1.0, delta=0.1)

        # Completed trace
        completed_ctx = self.engine.start_trace("completed_op")
        self.engine.end_trace(completed_ctx, Status.FAILURE)

        trace_details = self.engine.get_trace(completed_ctx.trace_id)
        self.assertEqual(trace_details["operation"], "completed_op")
        self.assertEqual(trace_details["status"], "failure")

        # Non-existent trace
        self.assertIsNone(self.engine.get_trace("invalid_id"))

    def test_trace_limit(self):
        """Test rotation of completed traces."""
        self.engine.max_completed_traces = 5

        for i in range(10):
            ctx = self.engine.start_trace(f"op_{i}")
            self.engine.end_trace(ctx, Status.SUCCESS)

        self.assertEqual(len(self.engine.completed_traces), 5)
        # Should contain op_5 to op_9
        ops = [t.operation for t in self.engine.completed_traces]
        self.assertIn("op_9", ops)
        self.assertNotIn("op_4", ops)

    def test_log_levels(self):
        """Test logging with different levels."""
        self.engine.log(LogLevel.INFO, "Info message")
        self.engine.log(LogLevel.WARN, "Warning message")
        self.engine.log(LogLevel.ERROR, "Error message")

        self.assertEqual(len(self.engine.logs), 3)
        self.assertEqual(self.engine.logs[0]["level"], "INFO")
        self.assertEqual(self.engine.logs[2]["level"], "ERROR")

    def test_query_logs(self):
        """Test querying logs."""
        self.engine.log(LogLevel.INFO, "User logged in")
        self.engine.log(LogLevel.ERROR, "Database connection failed")
        self.engine.log(LogLevel.INFO, "User logged out")

        # Filter by level
        error_logs = self.engine.query_logs(level=LogLevel.ERROR)
        self.assertEqual(len(error_logs), 1)
        self.assertEqual(error_logs[0]["message"], "Database connection failed")

        # Search text
        login_logs = self.engine.query_logs(search="logged")
        self.assertEqual(len(login_logs), 2)

        # Both
        not_found = self.engine.query_logs(level=LogLevel.ERROR, search="logged")
        self.assertEqual(len(not_found), 0)

    def test_log_rotation(self):
        """Test log rotation."""
        self.engine.max_logs = 5

        for i in range(10):
            self.engine.log(LogLevel.INFO, f"msg_{i}")

        self.assertEqual(len(self.engine.logs), 5)
        self.assertEqual(self.engine.logs[-1]["message"], "msg_9")
        self.assertEqual(self.engine.logs[0]["message"], "msg_5")

    def test_critical_alert(self):
        """Test that CRITICAL logs trigger alerts immediately."""
        self.engine.log(LogLevel.CRITICAL, "System meltdown")

        self.assertEqual(len(self.engine.alerts), 1)
        self.assertEqual(self.engine.alerts[0].severity, "critical")
        self.assertEqual(self.engine.alerts[0].message, "System meltdown")

        # Verify event emission
        self.mock_event_bus.emit_sync.assert_called_with(
            EventType.SYSTEM_ERROR,
            {
                "action": "critical_alert",
                "message": "System meltdown",
                "context": None
            },
            source="observability"
        )

    def test_high_error_rate_alert(self):
        """Test high error rate detection."""
        # 1. Add some success logs
        for i in range(8):
            self.engine.log(LogLevel.INFO, f"Success {i}")

        # 2. Add some error logs
        self.engine.log(LogLevel.ERROR, "Error 1")
        self.engine.log(LogLevel.ERROR, "Error 2")

        # 3. Check alerts
        new_alerts = self.engine.check_alerts()

        # Should have 1 alert for high error rate
        self.assertEqual(len(new_alerts), 1)
        self.assertEqual(new_alerts[0].name, "High Error Rate")
        self.assertIn("Error rate is 20.0%", new_alerts[0].message)

    def test_slow_response_alert(self):
        """Test slow response detection."""
        # Threshold is 10.0 seconds

        # 1. Add a normal trace
        ctx1 = self.engine.start_trace("fast_op")
        with patch('time.time', return_value=ctx1.start_time + 1.0):
            self.engine.end_trace(ctx1, Status.SUCCESS)

        # 2. Add a slow trace
        ctx2 = self.engine.start_trace("slow_op")
        with patch('time.time', return_value=ctx2.start_time + 15.0):
            self.engine.end_trace(ctx2, Status.SUCCESS)

        # 3. Check alerts
        new_alerts = self.engine.check_alerts()

        # Should have 1 alert for slow response
        self.assertEqual(len(new_alerts), 1)
        self.assertEqual(new_alerts[0].name, "Slow Response Detected")

    def test_performance_stats(self):
        """Test performance stats calculation."""
        self.engine.performance_stats["total_requests"] = 100
        self.engine.performance_stats["successful_requests"] = 90
        self.engine.performance_stats["failed_requests"] = 10
        self.engine.performance_stats["total_duration"] = 200.0

        stats = self.engine.get_performance_stats()

        self.assertEqual(stats["success_rate"], 0.9)
        self.assertEqual(stats["failure_rate"], 0.1)
        self.assertEqual(stats["avg_duration"], 2.0)

        # Test zero division safety
        self.engine.performance_stats["total_requests"] = 0
        stats_zero = self.engine.get_performance_stats()
        self.assertEqual(stats_zero["success_rate"], 0.0)

    @patch('cortex.observability.observability_engine')
    def test_global_helpers(self, mock_engine):
        """Test that global helper functions delegate to the singleton."""
        record_metric("metric", 1.0)
        mock_engine.record_metric.assert_called_with("metric", 1.0, None)

        start_trace("op")
        mock_engine.start_trace.assert_called_with("op", None)

        ctx = TraceContext(trace_id="1", operation="op")
        end_trace(ctx, Status.SUCCESS)
        mock_engine.end_trace.assert_called_with(ctx, Status.SUCCESS)

        log(LogLevel.INFO, "msg")
        mock_engine.log.assert_called_with(LogLevel.INFO, "msg", None)

        get_metrics("metric")
        mock_engine.get_metrics.assert_called_with("metric", None)

        get_trace("1")
        mock_engine.get_trace.assert_called_with("1")

        query_logs(level=LogLevel.ERROR)
        mock_engine.query_logs.assert_called_with(LogLevel.ERROR, None, 100)

        check_alerts()
        mock_engine.check_alerts.assert_called()

        get_performance_stats()
        mock_engine.get_performance_stats.assert_called()

if __name__ == '__main__':
    unittest.main()
