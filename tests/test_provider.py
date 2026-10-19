import json
import unittest
from unittest.mock import patch

from datarescue.dataset import Error
from datarescue.provider import Model


class ProviderTests(unittest.TestCase):
    def test_requires_remote_consent_and_tls(self):
        for url in ["http://example.org/v1", "https://example.org/v1", "http://localhost.evil/v1"]:
            with self.assertRaises(Error):
                Model("model", endpoint=url)
        with self.assertRaises(Error):
            Model("model", endpoint="http://example.org/v1", allow_remote=True)

    @patch("datarescue.provider.request_bytes")
    def test_real_wire_format_budget_usage(self, request):
        request.return_value = (
            200,
            {},
            json.dumps(
                {
                    "choices": [{"message": {"content": '{"proposals":[]}'}}],
                    "usage": {"prompt_tokens": 12, "completion_tokens": 4},
                }
            ).encode(),
        )
        model = Model("test", max_calls=1)
        self.assertEqual(model.complete({"profile": {}}), {"proposals": []})
        self.assertEqual(model.usage["prompt_tokens"], 12)
        body = json.loads(request.call_args.kwargs["body"])
        self.assertEqual(body["response_format"], {"type": "json_object"})
        self.assertLessEqual(body["max_tokens"], 2048)
        with self.assertRaises(Error):
            model.complete({})

    @patch("datarescue.provider.request_bytes")
    def test_failure_paths_do_not_expose_response_bodies(self, request):
        for status, body in [
            (401, b"secret-token"),
            (429, b"secret-token"),
            (302, b"redirect"),
            (200, b"not json"),
            (200, b'{"choices":[]}'),
        ]:
            request.return_value = status, {}, body
            with self.assertRaises(Error) as cm:
                Model("test").complete({})
            self.assertNotIn("secret-token", str(cm.exception))
