"""The paid smoke may expose only an approved diagnostic identifier."""

import unittest
from unittest.mock import Mock

from provider_walkthrough import Failed, check_turn, turn_error_code


class TurnErrorTests(unittest.TestCase):
    def test_only_exact_local_diagnostics_produce_specific_codes(self):
        for detail, code in [
            ("The provider returned an unsupported Join proposal.", "JOIN_PLAN_SCHEMA"),
            ("The repair references an unavailable Join.", "JOIN_REFERENCE_MISMATCH"),
            ("Provider returned HTTP 429. Check credentials, model and quota.", "UPSTREAM_HTTP_429"),
            ("Provider request failed or returned an incomplete structured answer.", "PROVIDER_TRANSPORT_OR_OUTPUT"),
            ("The provider returned an incomplete structured answer.", "PROVIDER_OUTPUT_INVALID"),
            ("Provider returned HTTP 429. Check credentials, model and quota. private-canary", "UNCLASSIFIED"),
            ({"input": "private-canary"}, "UNCLASSIFIED"),
            ("private-canary", "UNCLASSIFIED"),
        ]:
            response = Mock()
            response.json.return_value = {"detail": detail}
            self.assertEqual(turn_error_code(response), code)
        response.json.side_effect = ValueError("private-canary")
        self.assertEqual(turn_error_code(response), "UNCLASSIFIED")

    def test_rejected_turn_is_never_a_pass_and_keeps_its_code_when_verification_fails(self):
        response = Mock(ok=False, status=400)
        response.json.return_value = {"detail": "The repair references an unavailable Join."}
        code = "HTTP 400 [JOIN_REFERENCE_MISMATCH]"
        for snapshot, message in (
            (Mock(return_value="before"), code),
            (Mock(return_value="after"), code + ". A proposal changed server state before approval."),
            (Mock(side_effect=RuntimeError("private-canary")), code + ". Saved state could not be verified."),
        ):
            with self.assertRaises(Failed) as raised:
                check_turn(response, "before", snapshot)
            self.assertEqual(str(raised.exception), message)
            snapshot.assert_called_once()


if __name__ == "__main__":
    unittest.main()
