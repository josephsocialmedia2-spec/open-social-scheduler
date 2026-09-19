import importlib.util, json, os, tempfile, unittest
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
SPEC=importlib.util.spec_from_file_location("bridge",ROOT/"publisher"/"f1_seller_postiz_bridge.py")
bridge=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(bridge)

class TestSellerPostizBridge(unittest.TestCase):
    def test_territory_filter(self):
        s=bridge.territory_set({"sinistra":["Avigliana"],"destra":["Rosta"]})
        self.assertIn("avigliana",s); self.assertNotIn("milano",s)
    def test_postiz_bindings_are_separate(self):
        specs,missing=bridge.integration_specs({"postiz_integrations":{"facebook":{"id":"fb1","required":True},"instagram":{"id":"","required":True}}})
        self.assertEqual(specs,[{"platform":"facebook","integration_id":"fb1"}])
        self.assertEqual(missing,["instagram"])
    def test_slots_are_timezone_aware(self):
        from datetime import datetime
        now=datetime(2026,9,19,8,0,tzinfo=bridge.TZ)
        slots=bridge.next_slots(now,["09:00","14:00","19:00"],3)
        self.assertEqual([x.hour for x in slots],[9,14,19])
        self.assertTrue(all(x.tzinfo for x in slots))
if __name__=="__main__": unittest.main()
