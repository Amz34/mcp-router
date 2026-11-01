import unittest
from mcp_router.router import detect_intent, route_mcp_tools

class TestMCPRouter(unittest.TestCase):
    def test_intent_detection_bigquery(self):
        intents = detect_intent("Please query BigQuery dataset sales_2026")
        self.assertIn("gcp_bigquery", intents)

    def test_intent_detection_spanner(self):
        intents = detect_intent("Check Spanner DDL migrations for table customers")
        self.assertIn("gcp_spanner", intents)

    def test_intent_detection_none_for_pure_code(self):
        intents = detect_intent("Fix syntax error in python script and push git commit")
        self.assertEqual(len(intents), 0)

    def test_routing_minimal_profile(self):
        res = route_mcp_tools("Any text", explicit_profile="minimal")
        self.assertEqual(res.tools_selected, 0)
        self.assertEqual(len(res.active_servers), 0)
        self.assertGreater(res.tools_masked, 0)
        self.assertEqual(res.token_savings_pct, 100.0)

    def test_routing_data_profile(self):
        res = route_mcp_tools("Any text", explicit_profile="data")
        self.assertIn("dak_dak-bigquery", res.active_servers)
        self.assertNotIn("dak_dak-spanner", res.active_servers)
        self.assertGreater(res.token_savings_pct, 50.0)

    def test_sub_millisecond_routing_speed(self):
        res = route_mcp_tools("Audit postgres and bigquery data pipelines")
        self.assertLess(res.routing_latency_ms, 25.0)  # Must be fast and lightweight

if __name__ == "__main__":
    unittest.main()
