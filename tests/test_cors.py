import sys
import unittest
from fastapi.testclient import TestClient

sys.path.insert(0, ".")
from backend.main import app

class TestCORSPreflight(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app)

    def test_cors_vercel_regex(self):
        # 9. Test the exact preflight requested
        headers = {
            "Origin": "https://skylark-drones-dheeraj-submission.vercel.app",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type"
        }
        res = self.client.options("/chat/stream", headers=headers)
        self.assertIn(res.status_code, (200, 204))
        self.assertEqual(res.headers.get("access-control-allow-origin"), "https://skylark-drones-dheeraj-submission.vercel.app")
        
        # Test actual POST
        res_post = self.client.post(
            "/chat/stream", 
            json={"message": "hello", "history": []}, 
            headers={"Origin": "https://skylark-drones-dheeraj-submission.vercel.app"}
        )
        # Because we mocked nothing, it might fail inside chat_stream logic, 
        # but CORS headers should be attached.
        self.assertEqual(res_post.headers.get("access-control-allow-origin"), "https://skylark-drones-dheeraj-submission.vercel.app")

    def test_cors_vercel_other_allowed(self):
        # 10. Test other valid origins matching regex or explicit
        origins = [
            "https://skylark-drones-bi-motupallidheeraj21-gmailcoms-projects.vercel.app",
            "https://skylark-drones-git-c53403-motupallidheeraj21-gmailcoms-projects.vercel.app",
            "https://skylark-drones-rnhyvjkab-motupallidheeraj21-gmailcoms-projects.vercel.app"
        ]
        for origin in origins:
            res = self.client.options(
                "/chat/stream",
                headers={
                    "Origin": origin,
                    "Access-Control-Request-Method": "POST",
                    "Access-Control-Request-Headers": "content-type"
                }
            )
            self.assertIn(res.status_code, (200, 204))
            self.assertEqual(res.headers.get("access-control-allow-origin"), origin)

    def test_cors_disallowed_origin(self):
        # 11. Test a disallowed origin
        res = self.client.options(
            "/chat/stream",
            headers={
                "Origin": "https://example.com",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type"
            }
        )
        # CORSMiddleware returns 400 for bad preflight origin
        self.assertEqual(res.status_code, 400)
        self.assertIsNone(res.headers.get("access-control-allow-origin"))

    def test_cors_localhost(self):
        # 12. Test localhost
        res = self.client.options(
            "/chat/stream",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type"
            }
        )
        self.assertIn(res.status_code, (200, 204))
        self.assertEqual(res.headers.get("access-control-allow-origin"), "http://localhost:3000")

if __name__ == "__main__":
    unittest.main()
