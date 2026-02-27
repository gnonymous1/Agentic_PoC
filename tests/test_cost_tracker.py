import unittest
import sys
import os

# Add project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from core.monitoring import CostTracker

class TestCostTracker(unittest.TestCase):
    def setUp(self):
        self.tracker = CostTracker()

    def test_record_cost_zeros(self):
        """Test recording cost with zero values."""
        self.tracker.record_cost(
            provider="test_provider",
            model="test_model",
            input_tokens=0,
            output_tokens=0,
            cost_per_1k_input=0.0,
            cost_per_1k_output=0.0
        )

        self.assertEqual(self.tracker.get_daily_spend(), 0.0)
        self.assertEqual(self.tracker.per_provider_costs["test_provider"], 0.0)

        # Verify history entry
        last_entry = self.tracker.cost_history[-1]
        self.assertEqual(last_entry["input_tokens"], 0)
        self.assertEqual(last_entry["output_tokens"], 0)
        self.assertEqual(last_entry["cost_usd"], 0.0)

    def test_record_cost_normal(self):
        """Test recording cost with normal values."""
        # 1000 input tokens at $0.01 per 1k = $0.01
        # 2000 output tokens at $0.03 per 1k = $0.06
        # Total should be $0.07
        self.tracker.record_cost(
            provider="openai",
            model="gpt-4",
            input_tokens=1000,
            output_tokens=2000,
            cost_per_1k_input=0.01,
            cost_per_1k_output=0.03,
            agent="test_agent",
            task_type="test_task"
        )

        expected_cost = 0.07
        self.assertAlmostEqual(self.tracker.get_daily_spend(), expected_cost)
        self.assertAlmostEqual(self.tracker.per_provider_costs["openai"], expected_cost)
        self.assertAlmostEqual(self.tracker.per_agent_costs["test_agent"], expected_cost)
        self.assertAlmostEqual(self.tracker.per_task_costs["test_task"], expected_cost)

    def test_record_cost_mixed_zeros(self):
        """Test recording cost with some zero values (e.g. only input tokens)."""
        # 1000 input tokens at $0.01 per 1k = $0.01
        # 0 output tokens
        self.tracker.record_cost(
            provider="openai",
            model="gpt-4",
            input_tokens=1000,
            output_tokens=0,
            cost_per_1k_input=0.01,
            cost_per_1k_output=0.03
        )

        expected_cost = 0.01
        self.assertAlmostEqual(self.tracker.get_daily_spend(), expected_cost)

    def test_cost_reporting(self):
        """Test the cost report structure and values."""
        self.tracker.record_cost(
            provider="provider_a",
            model="model_a",
            input_tokens=1000,
            output_tokens=1000,
            cost_per_1k_input=0.01,
            cost_per_1k_output=0.01
        )
        # Cost = 0.01 + 0.01 = 0.02

        report = self.tracker.get_cost_report()

        self.assertIn("today_usd", report)
        self.assertIn("by_provider", report)
        self.assertIn("by_agent", report)
        self.assertIn("by_task", report)
        self.assertIn("total_all_time", report)
        self.assertIn("last_10_calls", report)

        self.assertAlmostEqual(report["today_usd"], 0.02)
        self.assertAlmostEqual(report["by_provider"]["provider_a"], 0.02)
        self.assertEqual(len(report["last_10_calls"]), 1)

if __name__ == '__main__':
    unittest.main()
