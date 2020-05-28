from unittest import TestCase

from rasa.core import run, utils

from turn_rasa_connector.turn import TurnInput


class TurnInputTests(TestCase):
    def setUp(self):
        self.input_channel = self._create_input_channel()
        self.app = run.configure_app([self.input_channel])

    def _create_input_channel(self):
        return TurnInput(hmac_secret="test-secret")

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

    def test_health(self):
        """
        Should return ok status
        """
        request, response = self.app.test_client.get("/webhooks/turn")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"status": "ok"})
