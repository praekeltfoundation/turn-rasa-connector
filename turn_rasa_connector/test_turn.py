from unittest import TestCase

from rasa.core import run, utils

from turn_rasa_connector.turn import TurnInput


class TurnInputTests(TestCase):
    def setUp(self):
        self.input_channel = self._create_input_channel()
        self.app = run.configure_app([self.input_channel])

    def _create_input_channel(self, hmac_secret=None):
        return TurnInput(hmac_secret=hmac_secret)

    def test_from_credentials(self):
        """
        Stores the credentials on the class
        """
        instance = TurnInput.from_credentials({"hmac_secret": "test-secret"})
        self.assertEqual(instance.hmac_secret, "test-secret")

    def test_no_credentials(self):
        """
        Raises an exception
        """
        with self.assertRaises(Exception):
            TurnInput.from_credentials({})

    def test_routes(self):
        """
        All routes should be set up correctly
        """
        routes = utils.list_routes(self.app)
        self.assertTrue(routes.get("turn_webhook.health").startswith("/webhooks/turn"))
        self.assertTrue(
            routes.get("turn_webhook.webhook").startswith("/webhooks/turn/webhook")
        )

    def test_health(self):
        """
        Should return ok status
        """
        request, response = self.app.test_client.get("/webhooks/turn")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "ok"})

    def test_validate_signature(self):
        """
        Should return whether a signature is valid or not
        """
        self.assertFalse(
            self.input_channel.validate_signature("secret", b"payload", "aW52YWxpZA==")
        )
        self.assertTrue(
            self.input_channel.validate_signature(
                "secret", b"payload", "uC/LeRrOxXhZuYm0MKgmSIzi5Hn9+SMmvQoug3WkK6Q="
            )
        )

    def test_webhook_invalid_signature(self):
        """
        Returns a 401 with an error message
        """
        self.input_channel = self._create_input_channel(hmac_secret="test-secret")
        self.app = run.configure_app([self.input_channel])

        request, response = self.app.test_client.post("/webhooks/turn/webhook", json={})
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json, {"error": "invalid_signature"})

        request, response = self.app.test_client.post(
            "/webhooks/turn/webhook",
            json={},
            headers={"X-Turn-Hook-Signature": "aW52YWxpZA=="},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json, {"error": "invalid_signature"})
