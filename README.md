# Turn Rasa Connector

_Currently ready and running in production_

A Rasa Connector for https://www.turn.io/

Handles Turn conversation claims

## Configuration
This connector has the following configuration:

url (required) - The URL of the Turn instance

token (required) - The authorization token to use when making requests to Turn

hmac_secret (optional) - If specified, validates that the HMAC signature in the webhook request is valid, returning an HTTP 401 if invalid

postgresql_url (optional) - If using PostgreSQL as a tracker store, ignores messages with message IDs that we've already processed (deduplication)

http_retries (optional) - Number of times to retry HTTP requests to Turn. Defaults to 3

Example credentials.yml:
```yaml
turn_rasa_connector.turn.TurnInput:
  url: "https://whatsapp.turn.io"
  token: "xxxxxxxxxxx"
  hmac_secret: "xxxx-xxxx-xxxx"
  postgresql_url: "postgres://"
  http_retries: 3
```

## Conversation Claims
This connector will handle receiving and extending the Turn conversation claim with
every message reply.

This is controlled by the `claim` key on the message:
- `extend` - This is the default if no claim key is supplied. Will extend the conversation claim.
- `release` - Will release the conversation claim.
- `revert` - Will release the conversation claim, and instead of sending the user a response, tell Turn Automation to process the last message, 

Example:
```yaml
utter_continue:
  - text: "What would you like to do?"
  # claim: extend
  # Is the default

utter_end:
  - text: "Thank you! Your conversation claim will now end"
    claim: release

utter_exit:
  - text: "this won't be sent"
  - claim: revert
```

## Development
Requires PostgreSQL. PostgreSQL location controlled using the TEST_POSTGRES_URL environment variable, defaulting to `postgres://`

```bash
~ pip install -r requirements.txt -r requirements-dev.txt
~ black .
~ isort -rc .
~ mypy .
~ flake8
~ py.test
```
