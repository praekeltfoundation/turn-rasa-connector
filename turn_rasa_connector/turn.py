import base64
import hmac
import json
import logging
from asyncio import wait
from datetime import datetime, timedelta
from typing import Any, Awaitable, Callable, Dict, List, Optional, Text
from urllib.parse import urljoin

import asyncpg
import httpx
from async_lru import alru_cache
from rasa.cli import utils as cli_utils
from rasa.core.channels import InputChannel, OutputChannel, UserMessage
from rasa.core.events import UserUttered
from sanic import Blueprint, response
from sanic.request import Request
from sanic.response import HTTPResponse

logger = logging.getLogger(__name__)


@alru_cache(maxsize=None)
async def get_media_id(turn_url: Text, turn_token: Text, url: Text):
    # TODO: Respect the caching headers from the URL, rather than indefinitely caching
    async with httpx.stream("GET", url) as image_response:
        image_response.raise_for_status()
        turn_response = await httpx.post(
            urljoin(turn_url, "/v1/media"),
            headers={
                "Authorization": f"Bearer {turn_token}",
                "Content-Type": image_response.headers["Content-Type"],
            },
            data=image_response.aiter_bytes(),
        )
        turn_response.raise_for_status()
        response_data: Any = turn_response.json()
        return response_data["media"][0]["id"]


class TurnOutput(OutputChannel):
    """
    Turn output channel
    """

    @classmethod
    def name(cls) -> Text:
        return "turn"

    def __init__(
        self, url: Text, token: Text, conversation_claim: Optional[Text] = None
    ):
        self.url = url
        self.token = token
        self.conversation_claim = conversation_claim
        super().__init__()

    async def _send_message(self, body: dict):
        headers = {"Authorization": f"Bearer {self.token}"}
        if self.conversation_claim:
            # TODO: End conversation claim at end of session
            headers["X-Turn-Claim-Extend"] = self.conversation_claim

        result = await httpx.post(
            urljoin(self.url, "/v1/messages"), headers=headers, json=body,
        )
        # TODO: Retries and error handling
        result.raise_for_status()

    async def send_response(self, recipient_id: Text, message: Dict[Text, Any]) -> None:
        # The Rasa implementation for this sends the text and the media part of the
        # message separately. For WhatsApp, we want to send this as a media message
        # with a text caption, so we handle it differently here
        if message.get("image"):
            await self.send_image_url(recipient_id, message.pop("image"), **message)
        elif message.get("custom"):
            await self.send_custom_json(recipient_id, message.pop("custom"), **message)
        elif message.get("buttons"):
            await self.send_text_with_buttons(
                recipient_id, message.pop("text"), message.pop("buttons"), **message
            )
        elif message.get("text"):
            await self.send_text_message(recipient_id, message.pop("text"), **message)
        else:
            raise NotImplementedError()

    async def send_text_message(
        self, recipient_id: Text, text: Text, **kwargs: Any
    ) -> None:
        await self._send_message(
            {"to": recipient_id, "type": "text", "text": {"body": text}}
        )

    async def send_image_url(
        self, recipient_id: Text, image: Text, text: Text = "", **kwargs: Any
    ) -> None:
        media_id = await get_media_id(self.url, self.token, image)
        image_obj = {"id": media_id}
        if text:
            image_obj["caption"] = text
        await self._send_message(
            {"to": recipient_id, "type": "image", "image": image_obj}
        )

    async def send_text_with_buttons(
        self,
        recipient_id: Text,
        text: Text,
        buttons: List[Dict[Text, Any]],
        **kwargs: Any,
    ) -> None:
        for idx, button in enumerate(buttons):
            text += "\n"
            text += cli_utils.button_to_string(button, idx)
        await self.send_text_message(recipient_id, text, **kwargs)

    async def send_custom_json(
        self, recipient_id: Text, json_message: Dict[Text, Any], **kwargs: Any
    ) -> None:
        json_message["to"] = recipient_id
        await self._send_message(json_message)

    # TODO: elements message type
    # TODO: attachment message type


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
            credentials.get("hmac_secret"),
            credentials["url"],
            credentials["token"],
            credentials.get("postgresql_url"),
        )

    def __init__(
        self,
        hmac_secret: Optional[Text],
        url: Text,
        token: Text,
        postgresql_url: Optional[Text],
    ) -> None:
        self.hmac_secret = hmac_secret
        self.url = url
        self.token = token
        self.postgresql_url = postgresql_url
        self._postgresql_pool = None

    async def get_postgresql_pool(self) -> Optional[asyncpg.pool.Pool]:
        if self._postgresql_pool is None and self.postgresql_url is not None:
            self._postgresql_pool = await asyncpg.create_pool(self.postgresql_url)
        return self._postgresql_pool

    async def message_processed(
        self, sender_id: Optional[Text], message_id: Optional[Text]
    ) -> bool:
        """
        Have we processed a message with this ID before
        """
        if not sender_id or not message_id:
            return False

        pool = await self.get_postgresql_pool()
        if pool is None:
            # If we don't have a postgresql config, don't deduplicate
            return False
        async with pool.acquire() as connection:
            async with connection.transaction():
                result = await connection.fetchval(
                    """
                    SELECT 1
                    FROM events
                    WHERE
                        sender_id = $1 AND
                        type_name = $2 AND
                        data::json ->> 'message_id' = $3 AND
                        timestamp > $4
                    LIMIT 1
                    """,
                    sender_id,
                    UserUttered.type_name,
                    message_id,
                    (datetime.utcnow() - timedelta(days=1)).timestamp(),
                )
                return result == 1

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
                messages = request.json.get("messages", [])
                assert isinstance(messages, list)
            except (TypeError, AttributeError, AssertionError):
                return response.json(
                    {"success": False, "error": "invalid_body"}, status=400
                )

            conversation_claim = request.headers.get("X-Turn-Claim", None)

            user_messages = []
            for message in messages:
                try:
                    message["conversation_claim"] = conversation_claim
                    processed = await self.message_processed(
                        message.get("from"), message.get("id")
                    )
                    if not processed:
                        user_messages.append(self.extract_message(message))
                except (TypeError, KeyError, AttributeError):
                    logger.warning(f"Invalid message: {json.dumps(message)}")
                    return response.json(
                        {"success": False, "error": "invalid_message"}, status=400
                    )

            if user_messages:
                # wait doesn't like empty lists
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

    def handle_common(self, text: Text, message: dict) -> UserMessage:
        return UserMessage(
            text=text,
            output_channel=self.get_output_channel(
                message.pop("conversation_claim", None)
            ),
            sender_id=message.pop("from"),
            input_channel=self.name(),
            message_id=message.pop("id"),
            metadata=message,
        )

    def handle_text(self, message: dict) -> UserMessage:
        return self.handle_common(message.pop("text")["body"], message)

    def handle_media(self, media_type: str, message: dict) -> UserMessage:
        return self.handle_common(message[media_type].pop("caption", ""), message)

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
        return self.handle_common("", message)

    def handle_location(self, message: dict) -> UserMessage:
        return self.handle_common("", message)

    def get_output_channel(
        self, conversation_claim: Optional[Text] = None
    ) -> OutputChannel:
        return TurnOutput(self.url, self.token, conversation_claim)
