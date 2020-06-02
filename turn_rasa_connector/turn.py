import base64
import hmac
import json
import logging
from asyncio import wait
from typing import Any, Awaitable, Callable, Dict, Optional, Text
from urllib.parse import urljoin

import httpx
from rasa.core.channels import InputChannel, OutputChannel, UserMessage
from sanic import Blueprint, response
from sanic.request import Request
from sanic.response import HTTPResponse

logger = logging.getLogger(__name__)


class TurnOutput(OutputChannel):
    """
    Turn output channel
    """

    @classmethod
    def name(cls) -> Text:
        return "turn"

    def __init__(self, url: Text, token: Text):
        self.url = url
        self.token = token
        super().__init__()

    async def _send_message(self, body: dict):
        result = await httpx.post(
            urljoin(self.url, "/v1/messages"),
            headers={"Authorization": f"Bearer {self.token}"},
            json=body,
        )
        result.raise_for_status()

    async def send_text_message(
        self, recipient_id: Text, text: Text, **kwargs: Any
    ) -> None:
        await self._send_message(
            {"to": recipient_id, "type": "text", "text": {"body": text}}
        )

    async def send_image_url(
        self, recipient_id: Text, image: Text, **kwargs: Any
    ) -> None:
        # TODO: Use media ID instead of image URL
        await self._send_message(
            {"to": recipient_id, "type": "image", "image": {"link": image}}
        )


class TurnInput(InputChannel):
    """
    Turn input channel
    """

    @classmethod
    def name(cls) -> Text:
        return "turn"

    @classmethod
    def from_credentials(cls, credentials: Dict[Text, Any]) -> InputChannel:
        if not credentials:
            cls.raise_missing_credentials_exception()

        return cls(
            credentials.get("hmac_secret"), credentials["url"], credentials["token"]
        )

    def __init__(self, hmac_secret: Optional[Text], url: Text, token: Text) -> None:
        self.hmac_secret = hmac_secret
        self.url = url
        self.token = token

    def blueprint(
        self, on_new_message: Callable[[UserMessage], Awaitable[Any]]
    ) -> Blueprint:
        turn_webhook = Blueprint("turn_webhook", __name__)

        @turn_webhook.route("/", methods=["GET"])
        async def health(request: Request) -> HTTPResponse:
            return response.json({"status": "ok"})

        @turn_webhook.route("/webhook", methods=["POST"])
        async def webhook(request: Request) -> HTTPResponse:
            if self.hmac_secret:
                signature = request.headers.get("X-Turn-Hook-Signature") or ""
                valid_signature = self.validate_signature(
                    self.hmac_secret, request.body, signature
                )
                if not valid_signature:
                    return response.json(
                        {"success": False, "error": "invalid_signature"}, status=401
                    )
            else:
                logging.warning("hmac_secret config not set, not validating signature")

            try:
                messages = request.json["messages"]
                assert isinstance(messages, list)
            except (TypeError, KeyError, AssertionError):
                return response.json(
                    {"success": False, "error": "invalid_body"}, status=400
                )

            user_messages = []
            for message in messages:
                try:
                    user_messages.append(self.extract_message(message))
                except (TypeError, KeyError, AttributeError):
                    logger.warning(f"Invalid message: {json.dumps(message)}")
                    return response.json(
                        {"success": False, "error": "invalid_message"}, status=400
                    )

            await wait(list(map(on_new_message, user_messages)))
            return response.json({"success": True})

        return turn_webhook

    @staticmethod
    def validate_signature(secret: Text, payload: bytes, signature: Text) -> bool:
        decoded_secret = secret.encode("utf8")
        decoded_signature = base64.b64decode(signature)
        digest = hmac.new(decoded_secret, payload, "sha256").digest()
        return hmac.compare_digest(digest, decoded_signature)

    def extract_message(self, message: dict) -> UserMessage:
        message_type = message["type"]
        handler = getattr(self, f"handle_{message_type}")
        return handler(message)

    def handle_common(self, text: Optional[str], message: dict) -> UserMessage:
        return UserMessage(
            text=text,
            output_channel=self.get_output_channel(),
            sender_id=message.pop("from"),
            input_channel=self.name(),
            message_id=message.pop("id"),
            metadata=message,
        )

    def handle_text(self, message: dict) -> UserMessage:
        return self.handle_common(message.pop("text")["body"], message)

    def handle_media(self, media_type: str, message: dict) -> UserMessage:
        return self.handle_common(message[media_type].pop("caption", None), message)

    def handle_audio(self, message: dict) -> UserMessage:
        return self.handle_media("audio", message)

    def handle_document(self, message: dict) -> UserMessage:
        return self.handle_media("document", message)

    def handle_image(self, message: dict) -> UserMessage:
        return self.handle_media("image", message)

    def handle_video(self, message: dict) -> UserMessage:
        return self.handle_media("video", message)

    def handle_voice(self, message: dict) -> UserMessage:
        return self.handle_media("voice", message)

    def handle_contacts(self, message: dict) -> UserMessage:
        return self.handle_common(None, message)

    def handle_location(self, message: dict) -> UserMessage:
        return self.handle_common(None, message)

    def get_output_channel(self) -> OutputChannel:
        return TurnOutput(self.url, self.token)
