from unittest import TestCase, mock

import pytest
from rasa.core import run, utils
from sanic import Sanic
from sanic.response import json

from turn_rasa_connector.turn import TurnInput, TurnOutput


class TurnInputTests(TestCase):
    def setUp(self):
        self.input_channel = self._create_input_channel()
        self.app = run.configure_app([self.input_channel])

    def _create_input_channel(
        self, hmac_secret=None, url="https://turn", token="testtoken"
    ):
        return TurnInput(hmac_secret=hmac_secret, url=url, token=token)

    def test_from_credentials(self):
        """
        Stores the credentials on the class
        """
        instance = TurnInput.from_credentials(
            {"hmac_secret": "test-secret", "url": "https://turn", "token": "testtoken"}
        )
        self.assertEqual(instance.hmac_secret, "test-secret")
        self.assertEqual(instance.url, "https://turn")
        self.assertEqual(instance.token, "testtoken")

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
        self.assertEqual(message.metadata, {"timestamp": "1518694235", "type": "text"})

    def test_webhook_handle_invalid_messages(self):
        """
        Returns an invalid message error
        """
        request, response = self.app.test_client.post(
            "/webhooks/turn/webhook", json={"messages": [{"type": "invalid"}]},
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json, {"success": False, "error": "invalid_message"})

    def test_handle_audio(self):
        """
        Returns a UserMesssage with valid parameters
        """
        message = self.input_channel.extract_message(
            {
                "from": "27820001001",
                "id": "ABGGFlA5FpafAgo6tHcNmNjXmuSf",
                "audio": {
                    "file": "/usr/local/wamedia/shared/b1cf38-8734-4ad3-b4a1-ef0c10d0d",
                    "id": "b1c68f38-8734-4ad3-b4a1-ef0c10d683",
                    "mime_type": "audio/mpeg",
                    "sha256": "29ed500fa64eb55fc19dc4124acb300e5dcc54a0f822a301ae99944",
                },
                "timestamp": "1521497954",
                "type": "audio",
            }
        )
        self.assertEqual(message.text, None)
        self.assertEqual(message.sender_id, "27820001001")
        self.assertEqual(message.message_id, "ABGGFlA5FpafAgo6tHcNmNjXmuSf")
        self.assertEqual(
            message.metadata,
            {
                "audio": {
                    "file": "/usr/local/wamedia/shared/b1cf38-8734-4ad3-b4a1-ef0c10d0d",
                    "id": "b1c68f38-8734-4ad3-b4a1-ef0c10d683",
                    "mime_type": "audio/mpeg",
                    "sha256": "29ed500fa64eb55fc19dc4124acb300e5dcc54a0f822a301ae99944",
                },
                "timestamp": "1521497954",
                "type": "audio",
            },
        )

    def test_handle_document(self):
        """
        Returns a UserMessage with valid parameters
        """
        message = self.input_channel.extract_message(
            {
                "from": "27820001001",
                "id": "ABGGFlA5FpafAgo6tHcNmNjXmuSf",
                "timestamp": "1522189546",
                "type": "document",
                "document": {
                    "caption": "80skaraokesonglistartist",
                    "file": "/usr/local/wamedia/shared/fc233119-733f-49c-bcbd-b2f68f79",
                    "id": "fc233119-733f-49c-bcbd-b2f68f798e33",
                    "mime_type": "application/pdf",
                    "sha256": "3b11fa6ef2bde1dd14726e09d3edaf782120919d06f6484f32d5d5c",
                },
            }
        )
        self.assertEqual(message.text, "80skaraokesonglistartist")
        self.assertEqual(message.sender_id, "27820001001")
        self.assertEqual(message.message_id, "ABGGFlA5FpafAgo6tHcNmNjXmuSf")
        self.assertEqual(
            message.metadata,
            {
                "document": {
                    "file": "/usr/local/wamedia/shared/fc233119-733f-49c-bcbd-b2f68f79",
                    "id": "fc233119-733f-49c-bcbd-b2f68f798e33",
                    "mime_type": "application/pdf",
                    "sha256": "3b11fa6ef2bde1dd14726e09d3edaf782120919d06f6484f32d5d5c",
                },
                "timestamp": "1522189546",
                "type": "document",
            },
        )

    def test_handle_image(self):
        """
        Returns a UserMessage with valid parameters
        """
        message = self.input_channel.extract_message(
            {
                "from": "27820001001",
                "id": "ABGGFlA5FpafAgo6tHcNmNjXmuSf",
                "image": {
                    "file": "/usr/local/wamedia/shared/b1cf38-8734-4ad3-b4a1-ef0c10d0d",
                    "id": "b1c68f38-8734-4ad3-b4a1-ef0c10d683",
                    "mime_type": "image/jpeg",
                    "sha256": "29ed500fa64eb55fc19dc4124acb300e5dcc54a0f822a301ae99944",
                    "caption": "Check out my new phone!",
                },
                "timestamp": "1521497954",
                "type": "image",
            }
        )
        self.assertEqual(message.text, "Check out my new phone!")
        self.assertEqual(message.sender_id, "27820001001")
        self.assertEqual(message.message_id, "ABGGFlA5FpafAgo6tHcNmNjXmuSf")
        self.assertEqual(
            message.metadata,
            {
                "image": {
                    "file": "/usr/local/wamedia/shared/b1cf38-8734-4ad3-b4a1-ef0c10d0d",
                    "id": "b1c68f38-8734-4ad3-b4a1-ef0c10d683",
                    "mime_type": "image/jpeg",
                    "sha256": "29ed500fa64eb55fc19dc4124acb300e5dcc54a0f822a301ae99944",
                },
                "timestamp": "1521497954",
                "type": "image",
            },
        )

    def test_handle_video(self):
        """
        Returns a UserMessage with valid parameters
        """
        message = self.input_channel.extract_message(
            {
                "from": "27820001001",
                "id": "ABGGFlA5FpafAgo6tHcNmNjXmuSf",
                "video": {
                    "file": "/usr/local/wamedia/shared/b1cf38-8734-4ad3-b4a1-ef0c10d0d",
                    "id": "b1c68f38-8734-4ad3-b4a1-ef0c10d683",
                    "mime_type": "video/mp4",
                    "sha256": "29ed500fa64eb55fc19dc4124acb300e5dcc54a0f822a301ae99944",
                    "caption": "Check out my new phone!",
                },
                "timestamp": "1521497954",
                "type": "video",
            }
        )
        self.assertEqual(message.text, "Check out my new phone!")
        self.assertEqual(message.sender_id, "27820001001")
        self.assertEqual(message.message_id, "ABGGFlA5FpafAgo6tHcNmNjXmuSf")
        self.assertEqual(
            message.metadata,
            {
                "video": {
                    "file": "/usr/local/wamedia/shared/b1cf38-8734-4ad3-b4a1-ef0c10d0d",
                    "id": "b1c68f38-8734-4ad3-b4a1-ef0c10d683",
                    "mime_type": "video/mp4",
                    "sha256": "29ed500fa64eb55fc19dc4124acb300e5dcc54a0f822a301ae99944",
                },
                "timestamp": "1521497954",
                "type": "video",
            },
        )

    def test_handle_voice(self):
        """
        Returns a UserMessage with valid parameters
        """
        message = self.input_channel.extract_message(
            {
                "from": "27820001001",
                "id": "ABGGFlA5FpafAgo6tHcNmNjXmuSf",
                "timestamp": "1521827831",
                "type": "voice",
                "voice": {
                    "file": "/usr/local/wamedia/shared/463e/b7ec/ff4e4d9bb1101879cbd41",
                    "id": "463eb7ec-ff4e-4d9b-b110-1879cbd411b2",
                    "mime_type": "audio/ogg; codecs=opus",
                    "sha256": "fa9e1807d936b7cebe63654ea3a7912b1fa9479220258d823590521",
                },
            }
        )
        self.assertEqual(message.text, None)
        self.assertEqual(message.sender_id, "27820001001")
        self.assertEqual(message.message_id, "ABGGFlA5FpafAgo6tHcNmNjXmuSf")
        self.assertEqual(
            message.metadata,
            {
                "voice": {
                    "file": "/usr/local/wamedia/shared/463e/b7ec/ff4e4d9bb1101879cbd41",
                    "id": "463eb7ec-ff4e-4d9b-b110-1879cbd411b2",
                    "mime_type": "audio/ogg; codecs=opus",
                    "sha256": "fa9e1807d936b7cebe63654ea3a7912b1fa9479220258d823590521",
                },
                "timestamp": "1521827831",
                "type": "voice",
            },
        )

    def test_handle_contacts(self):
        """
        Returns a UserMessage with valid parameters
        """
        message = self.input_channel.extract_message(
            {
                "contacts": [
                    {
                        "addresses": [
                            {
                                "city": "Menlo Park",
                                "country": "United States",
                                "country_code": "us",
                                "state": "CA",
                                "street": "1 Hacker Way",
                                "type": "WORK",
                                "zip": "94025",
                            }
                        ],
                        "birthday": "2012-08-18",
                        "contact_image": "/9j/4AAQSkZJRgABAQEAZABkAAD/2wBDAAgGBgcGBQgH",
                        "emails": [{"email": "kfish@fb.com", "type": "WORK"}],
                        "ims": [{"service": "AIM", "user_id": "kfish"}],
                        "name": {
                            "first_name": "Kerry",
                            "formatted_name": "Kerry Fisher",
                            "last_name": "Fisher",
                        },
                        "org": {"company": "Facebook"},
                        "phones": [
                            {"phone": "+1 (940) 555-1234", "type": "CELL"},
                            {
                                "phone": "+1 (650) 555-1234",
                                "type": "WORK",
                                "wa_id": "16505551234",
                            },
                        ],
                        "urls": [{"url": "https://www.facebook.com", "type": "WORK"}],
                    }
                ],
                "from": "16505551234",
                "id": "ABGGFlA4dSRvAgo6C4Z53hMh1ugR",
                "timestamp": "1537248012",
                "type": "contacts",
            }
        )
        self.assertEqual(message.text, None)
        self.assertEqual(message.sender_id, "16505551234")
        self.assertEqual(message.message_id, "ABGGFlA4dSRvAgo6C4Z53hMh1ugR")
        self.assertEqual(
            message.metadata,
            {
                "contacts": [
                    {
                        "addresses": [
                            {
                                "city": "Menlo Park",
                                "country": "United States",
                                "country_code": "us",
                                "state": "CA",
                                "street": "1 Hacker Way",
                                "type": "WORK",
                                "zip": "94025",
                            }
                        ],
                        "birthday": "2012-08-18",
                        "contact_image": "/9j/4AAQSkZJRgABAQEAZABkAAD/2wBDAAgGBgcGBQgH",
                        "emails": [{"email": "kfish@fb.com", "type": "WORK"}],
                        "ims": [{"service": "AIM", "user_id": "kfish"}],
                        "name": {
                            "first_name": "Kerry",
                            "formatted_name": "Kerry Fisher",
                            "last_name": "Fisher",
                        },
                        "org": {"company": "Facebook"},
                        "phones": [
                            {"phone": "+1 (940) 555-1234", "type": "CELL"},
                            {
                                "phone": "+1 (650) 555-1234",
                                "type": "WORK",
                                "wa_id": "16505551234",
                            },
                        ],
                        "urls": [{"url": "https://www.facebook.com", "type": "WORK"}],
                    }
                ],
                "timestamp": "1537248012",
                "type": "contacts",
            },
        )

    def test_handle_location(self):
        """
        Returns a UserMessage with valid parameters
        """
        message = self.input_channel.extract_message(
            {
                "from": "16315551234",
                "id": "ABGGFlA5FpafAgo6tHcNmNjXmuSf",
                "location": {
                    "address": "Main Street Beach, Santa Cruz, CA",
                    "latitude": 38.9806263495,
                    "longitude": -131.9428612257,
                    "name": "Main Street Beach",
                    "url": "https://foursquare.com/v/4d7031d35b5df7744",
                },
                "timestamp": "1521497875",
                "type": "location",
            }
        )
        self.assertEqual(message.text, None)
        self.assertEqual(message.sender_id, "16315551234")
        self.assertEqual(message.message_id, "ABGGFlA5FpafAgo6tHcNmNjXmuSf")
        self.assertEqual(
            message.metadata,
            {
                "location": {
                    "address": "Main Street Beach, Santa Cruz, CA",
                    "latitude": 38.9806263495,
                    "longitude": -131.9428612257,
                    "name": "Main Street Beach",
                    "url": "https://foursquare.com/v/4d7031d35b5df7744",
                },
                "timestamp": "1521497875",
                "type": "location",
            },
        )


def test_output_channel_name():
    """
    Test that the output channel's name is correct
    """
    output_channel = TurnOutput(url="https://turn", token="testtoken")
    assert output_channel.name() == "turn"


@pytest.fixture
def turn_mock_server(loop, test_client):
    app = Sanic("mock_turn")
    app.messages = []

    @app.route("/v1/messages", methods=["POST"])
    async def messages(request):
        app.messages.append(request)
        return json({})

    return loop.run_until_complete(test_client(app))


@pytest.mark.asyncio
async def test_send_text_message(turn_mock_server: Sanic):
    """
    Makes an HTTP request to Turn to send the message
    """
    output_channel = TurnOutput(
        url=f"http://{turn_mock_server.host}:{turn_mock_server.port}", token="testtoken"
    )
    await output_channel.send_response("27820001001", {"text": "test message"})
    [message] = turn_mock_server.app.messages
    assert message.json == {
        "to": "27820001001",
        "type": "text",
        "text": {"body": "test message"},
    }
    assert message.headers["Authorization"] == "Bearer testtoken"
    assert message.headers["Content-Type"] == "application/json"


@pytest.mark.asyncio
async def test_send_image_message(turn_mock_server: Sanic):
    """
    Makes an HTTP request to Turn to send the message
    """
    output_channel = TurnOutput(
        url=f"http://{turn_mock_server.host}:{turn_mock_server.port}", token="testtoken"
    )
    await output_channel.send_response(
        "27820001001", {"image": "https://example.org/image.jpg"}
    )
    [message] = turn_mock_server.app.messages
    assert message.json == {
        "to": "27820001001",
        "type": "image",
        "image": {"link": "https://example.org/image.jpg"},
    }
    assert message.headers["Authorization"] == "Bearer testtoken"
    assert message.headers["Content-Type"] == "application/json"


@pytest.mark.asyncio
async def test_send_text_with_buttons_message(turn_mock_server: Sanic):
    """
    Makes an HTTP request to Turn to send the message
    """
    output_channel = TurnOutput(
        url=f"http://{turn_mock_server.host}:{turn_mock_server.port}", token="testtoken"
    )
    await output_channel.send_response(
        "27820001001",
        {"text": "test message", "buttons": [{"title": "item1"}, {"title": "item2"}]},
    )
    [message] = turn_mock_server.app.messages
    assert message.json == {
        "to": "27820001001",
        "type": "text",
        "text": {"body": "test message\n1: item1\n2: item2"},
    }
    assert message.headers["Authorization"] == "Bearer testtoken"
    assert message.headers["Content-Type"] == "application/json"


@pytest.mark.asyncio
async def test_send_custom_message(turn_mock_server: Sanic):
    """
    Makes an HTTP request to Turn to send the message
    """
    output_channel = TurnOutput(
        url=f"http://{turn_mock_server.host}:{turn_mock_server.port}", token="testtoken"
    )
    await output_channel.send_response(
        "27820001001", {"custom": {"type": "text", "text": {"body": "test message"}}},
    )
    [message] = turn_mock_server.app.messages
    assert message.json == {
        "to": "27820001001",
        "type": "text",
        "text": {"body": "test message"},
    }
    assert message.headers["Authorization"] == "Bearer testtoken"
    assert message.headers["Content-Type"] == "application/json"
