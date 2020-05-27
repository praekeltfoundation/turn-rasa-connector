from typing import Any, Awaitable, Callable, Dict, Optional, Text

from rasa.core.channels import InputChannel, UserMessage
from sanic import Blueprint, response
from sanic.request import Request
from sanic.response import HTTPResponse


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

        return turn_webhook
