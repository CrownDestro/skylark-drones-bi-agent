import unittest
import sys

sys.path.insert(0, ".")

from backend.analytics.cross_board import cross_board_sector_analysis
from backend.analytics.pipeline import calculate_pipeline, _is_open

class TestPipelineRegression(unittest.TestCase):
    def setUp(self):
        self.mock_deals = [
            {"name": "Open Deal 1", "sector": "Tender", "deal_value": 50000000, "deal_status": "Open", "closure_probability": "High"},
            {"name": "Open Deal 2", "sector": "Tender", "deal_value": 3200000, "deal_status": "Open", "closure_probability": "Medium"},
            {"name": "Won Deal", "sector": "Tender", "deal_value": 10000000, "deal_status": "Won", "closure_probability": "High"},
            {"name": "Lost Deal", "sector": "Powerline", "deal_value": 5000000, "deal_status": "Lost", "closure_probability": "Low"},
            {"name": "Empty Status Deal", "sector": "Powerline", "deal_value": 20000000, "deal_status": None, "closure_probability": "High"},
            {"name": "In Progress Deal", "sector": "Powerline", "deal_value": 30000000, "deal_status": "In Progress", "closure_probability": "High"},
            {"name": "Open Deal 3", "sector": "Powerline", "deal_value": 6300000, "deal_status": "Open", "closure_probability": "High"},
        ]
        self.mock_wos = []

    def test_is_open_strict_definition(self):
        """Pipeline must strictly mean OPEN deals."""
        open_deals = [d for d in self.mock_deals if _is_open(d)]
        self.assertEqual(len(open_deals), 3)
        self.assertEqual(open_deals[0]["name"], "Open Deal 1")
        self.assertEqual(open_deals[1]["name"], "Open Deal 2")
        self.assertEqual(open_deals[2]["name"], "Open Deal 3")

    def test_calculate_pipeline_strict(self):
        """calculate_pipeline should only count Open deals."""
        res = calculate_pipeline(self.mock_deals)
        self.assertEqual(res["open_deal_count"], 3)
        
        # Total pipeline should be 50M + 3.2M + 6.3M = 59.5M
        self.assertEqual(res["total_pipeline"], 59500000)

        # Tender sector should be 53.2M
        self.assertEqual(res["sector_breakdown"]["Tender"]["value"], 53200000)
        
        # Powerline sector should be 6.3M
        self.assertEqual(res["sector_breakdown"]["Powerline"]["value"], 6300000)

    def test_cross_board_strict(self):
        """cross_board_sector_analysis should only count Open deals in the pipeline column."""
        res = cross_board_sector_analysis(self.mock_deals, self.mock_wos)
        
        tender_res = next(s for s in res["sectors"] if s["sector"] == "Tender")
        powerline_res = next(s for s in res["sectors"] if s["sector"] == "Powerline")
        
        self.assertEqual(tender_res["pipeline"], 53200000)
        self.assertEqual(powerline_res["pipeline"], 6300000)
        
        # Won, Lost, and unclassified deals shouldn't inflate the pipeline
        self.assertEqual(res["total_pipeline"], 59500000)


if __name__ == "__main__":
    unittest.main()
