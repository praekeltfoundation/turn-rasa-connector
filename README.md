# Turn Rasa Connector

_Currently under development_

A Rasa Connector for https://www.turn.io/

Handles Turn conversation claims

## Configuration
This connector has the following configuration:

url (required) - The URL of the Turn instance

token (required) - The authorization token to use when making requests to Turn

hmac_secret (optional) - If specified, validates that the HMAC signature in the webhook request is valid, returning an HTTP 401 if invalid

postgresql_url (optional) - If using PostgreSQL as a tracker store, ignores messages with message IDs that we've already processed (deduplication)

Example:
```yaml
turn_rasa_connector.turn.TurnInput:
  url: "https://whatsapp.turn.io"
  token: "xxxxxxxxxxx"
  hmac_secret: "xxxx-xxxx-xxxx"
  postgresql_url: "postgres://
```

## Development
```bash
~ pip install -r requirements.txt -r requirements-dev.txt
~ black .
~ isort -rc .
~ mypy .
~ flake8
~ py.test
```
