import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(__file__))

from backend import APP as backend_app
from backend import CURRENT_CONTEXT_WINDOW_TOKENS
from inference_engine import AX650Backend


class ContextWindowTests(unittest.TestCase):
    def test_backend_can_update_context_window(self):
        backend = AX650Backend()
        self.assertEqual(backend.context_window_tokens, 1024)

        updated = backend.set_context_window(2048)
        self.assertEqual(updated, 2048)
        self.assertEqual(backend.context_window_tokens, 2048)

    def test_service_config_endpoint_updates_context_window(self):
        original = CURRENT_CONTEXT_WINDOW_TOKENS
        try:
            with backend_app.test_client() as client:
                response = client.get("/config/context-window")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json()["context_window_tokens"], 1024)

                response = client.post(
                    "/config/context-window",
                    json={"context_window_tokens": 2048},
                )
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json()["context_window_tokens"], 2048)

                response = client.get("/config/context-window")
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json()["context_window_tokens"], 2048)
        finally:
            import backend as backend_module
            backend_module.CURRENT_CONTEXT_WINDOW_TOKENS = original


if __name__ == "__main__":
    unittest.main()
