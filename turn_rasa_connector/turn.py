import base64
import hmac
import json
import logging
from asyncio import wait
from typing import Any, Awaitable, Callable, Dict, Optional, Text

from rasa.core.channels import InputChannel, UserMessage
from sanic import Blueprint, response
from sanic.request import Request
from sanic.response import HTTPResponse

logger = logging.getLogger(__name__)


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

        return cls(credentials.get("hmac_secret"))

    def __init__(self, hmac_secret: Optional[Text]) -> None:
        self.hmac_secret = hmac_secret

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

            user_messages = list(map(self.extract_message, messages))
            if not all(user_messages):
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
        message_type = None
        try:
            message_type = message.pop("type")
            handler = getattr(self, f"handle_{message_type}")
            return handler(message)
        except (TypeError, KeyError, AttributeError):
            logger.warning(f"Invalid message type: {message_type}")
            return None

    def handle_text(self, message: dict) -> UserMessage:
        try:
            return UserMessage(
                text=message.pop("text")["body"],
                # TODO: Create output channel for responses
                output_channel=None,
                sender_id=message.pop("from"),
                input_channel=self.name(),
                message_id=message.pop("id"),
                metadata=message,
            )
        except (TypeError, KeyError):
            logger.warning(f"Invalid message: {json.dumps(message)}")
            return None

    def handle_media(self, media_type: str, message: dict) -> UserMessage:
        try:
            return UserMessage(
                text=message[media_type].pop("caption", None),
                # TODO: Create output channel for responses
                output_channel=None,
                sender_id=message.pop("from"),
                input_channel=self.name(),
                message_id=message.pop("id"),
                metadata=message,
            )
        except (TypeError, KeyError):
            logger.warning(f"Invalid message: {json.dumps(message)}")
            return None

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
        try:
            return UserMessage(
                text=None,
                # TODO: Create output channel for responses
                output_channel=None,
                sender_id=message.pop("from"),
                input_channel=self.name(),
                message_id=message.pop("id"),
                metadata=message,
            )
        except (TypeError, KeyError):
            logger.warning(f"Invalid message: {json.dumps(message)}")
            return None

    def handle_location(self, message: dict) -> UserMessage:
        raise NotImplementedError
