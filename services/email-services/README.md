# Email Service

Transactional email delivery for Identyx. Consumes events from the Redpanda
stream (Kafka) and sends emails over SMTP (Brevo). If the service is down,
messages are persisted in the broker and consumed later — no email is lost.

## Role

- **Event-driven** — consumes `user.registered`, `auth.suspicious`,
  `auth.new_login`, `user.deletion_requested` and `user.email_change_requested`
  events published by the auth-service and dispatches them to handlers.
- **Verification email** — sends the email-verification link after registration.
- **Suspicious-login alert** — notifies the account owner on brute-force lockout.
- **New-login alert** — sends a security email with device and IP-geolocation
  details when a login occurs from a new device/location.
- **Account deletion confirmation** — sends the one-time confirmation link
  (`user.deletion_requested`) to the account owner.
- **Email-change confirmation** — sends the one-time confirmation link
  (`user.email_change_requested`) to the **new** address.
- **Direct internal API** — `POST /emails/*` routes (hidden from the schema,
  protected by `X-Internal-Key`) allow sending verification and password-reset
  emails on demand.

## Tech stack

- FastAPI + uvicorn
- aiokafka (Kafka consumer via Redpanda, consumer group `email-service-group`)
- aiosmtplib / SMTP (smtp-relay.brevo.com, STARTTLS)

## Consumed topics

| Topic | Handler | Email sent |
|---|---|---|
| `user.registered` | `handler_user_registered` | Email verification link |
| `auth.suspicious` | `handler_auth_suspicious` | Suspicious-login / lockout alert |
| `auth.new_login` | `handler_new_login` | New-device login alert (device + IP geolocation) |

## Endpoints

Internal only (never exposed through the gateway):

| Method | Path | Summary |
|---|---|---|
| POST | `/emails/send-verification` | Send the verification email |
| POST | `/emails/send-reset-password` | Send the password-reset email |

## Configuration

All variables are read from the root `.env`:

| Variable | Default | Description |
|---|---|---|
| `EMAIL_SERVICE_PORT` | `8005` | Listening port |
| `SMTP_HOST` | `smtp-relay.brevo.com` | SMTP relay host |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USER` / `SMTP_PASSWORD` | — | Brevo (SMTP) credentials |
| `SMTP_USE_TLS` | `true` | Enable STARTTLS |
| `KAFKA_BOOTSTRAP_SERVERS` | `redpanda:9092` | Event broker |
| `KAFKA_CONSUMER_GROUP_ID` | `email-service-group` | Consumer group |
| `INTERNAL_API_KEY` | — | Shared secret for internal calls (`X-Internal-Key`) |

## Running locally

From the repository root, the service runs inside the full stack:

```bash
docker compose -f infra/docker-compose.yml up -d --build
```

Or run it standalone against the stack (reload for development):

```bash
uv sync
uv run uvicorn app.main:app --reload --port 8005
```

## Tests

```bash
uv run pytest
```

End-to-end tests for the whole platform live in
[`tests/e2e`](../../tests/e2e).

## Project layout

```
app/
├── api/
│   └── routes/emails.py   # internal send endpoints
├── core/config.py         # pydantic-settings configuration
├── events/
│   ├── subscriber.py      # Kafka consumer (EventSubscriber)
│   ├── handlers.py        # per-topic email handlers
│   └── types.py           # topic name constants
├── services/              # email rendering + SMTP delivery
└── main.py                # FastAPI app, wires handlers to topics
```

Full API documentation: [`docs/api/APIDOG.md`](../../docs/api/APIDOG.md).
