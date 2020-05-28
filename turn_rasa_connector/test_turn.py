from unittest import TestCase, mock

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
        self.assertEqual(
            response.json, {"error": "invalid_signature", "success": False}
        )

        request, response = self.app.test_client.post(
            "/webhooks/turn/webhook",
            json={},
            headers={"X-Turn-Hook-Signature": "aW52YWxpZA=="},
        )
        self.assertEqual(response.status_code, 401)
        self.assertEqual(
            response.json, {"error": "invalid_signature", "success": False}
        )

    def test_webhook_invalid_body(self):
        """
        If the body isn't a valid json object, then we should return an error message
        """
        request, response = self.app.test_client.post(
            "/webhooks/turn/webhook", data="invalid"
        )
        self.assertEqual(response.status_code, 400)

        request, response = self.app.test_client.post(
            "/webhooks/turn/webhook", data="[]"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {"error": "invalid_body", "success": False})

        request, response = self.app.test_client.post(
            "/webhooks/turn/webhook", data="{}"
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {"error": "invalid_body", "success": False})

        request, response = self.app.test_client.post(
            "/webhooks/turn/webhook", data='{"messages": "invalid"}'
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {"error": "invalid_body", "success": False})

    def test_webhook_handle_valid_messages(self):
        """
        Should process the messages
        """
        self.app.agent = mock.Mock()
        request, response = self.app.test_client.post(
            "/webhooks/turn/webhook",
            json={
                "messages": [
                    {
                        "type": "text",
                        "text": {"body": "message body"},
                        "from": "27820001001",
                        "id": "message-id",
                        "timestamp": "1518694235",
                    }
                ]
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json, {"success": True})

        [call] = self.app.agent.handle_message.call_args_list
        args, kwargs = call
        [message] = args
        self.assertEqual(message.text, "message body")
        self.assertEqual(message.sender_id, "27820001001")
        self.assertEqual(message.message_id, "message-id")
        self.assertEqual(message.metadata, {"timestamp": "1518694235"})

    def test_webhook_handle_invalid_messages(self):
        """
        Returns an invalid message error
        """
        request, response = self.app.test_client.post(
            "/webhooks/turn/webhook", json={"messages": [{"type": "invalid"}]},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {"success": False, "error": "invalid_message"})

    def test_handle_text_invalid(self):
        """
        Should return None for invalid messages
        """
        msg = self.input_channel.handle_text({})
        self.assertEqual(msg, None)
