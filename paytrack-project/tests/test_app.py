import os
import sys
import unittest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "api")))
os.environ.setdefault("DATABASE_URL", "postgresql+psycopg://test:test@localhost:5432/test")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
from app import app

class PayTrackApiTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

    def test_liveness(self):
        response = self.client.get("/api/health/live")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json["status"], "ok")

    @patch("app.init_db")
    def test_create_payment_validates_required_fields(self, init_db):
        response = self.client.post("/api/payments", json={"customer_name": "", "amount": 12, "reference": "X"})
        self.assertEqual(response.status_code, 400)

    @patch("app.init_db")
    @patch("app.engine")
    def test_list_payments_returns_json_list(self, engine, init_db):
        connection = MagicMock()
        engine.connect.return_value.__enter__.return_value = connection
        connection.execute.return_value.mappings.return_value.all.return_value = []
        response = self.client.get("/api/payments")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, [])

if __name__ == "__main__":
    unittest.main()
