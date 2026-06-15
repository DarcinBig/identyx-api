import redis.asyncio as aioredis

class EventPublisher:
    """
    Publishes events to Redis Pub/Sub channels.

    Fire & forget — if Redis is unavailable, the event
    is silently lost. In future versions, RabbitMQ/Kafka
    will guarantee at-least-once delivery.
    """
    def __init__(self, redis_url: str):
        self._redis_url = redis_url
        self._client: aioredis.Redis | None = None

    async def connect(self) -> None:
        """Initializes Redis connection."""
        self._client = aioredis.from_url(
            self._redis_url,
            encoding="utf-8",
            decode_responses=True,
        )
        await self._client.ping()
        print(f"[EventPublisher] Connected to Redis")

    async def close(self) -> None:
        """Closes Redis connection."""
        if self._client:
            await self._client.aclose()
            self._client = None

    async def publish(self, channel: str, event) -> None:
        """
        Publishes an event to a Redis channel.

        Args:
            channel : channel name (e.g., "user.registered")
            event   : instance of an event dataclass with .to_json()

        Never throws an exception — fire and forget.
        """
        if not self._client:
            print(f"[EventPublisher] WARNING: not connected, event lost on '{channel}'")
            return
        try:
            payload = event.to_json()
            subscribers = await self._client.publish(channel, payload)
            print(f"[EventPublisher] Published to '{channel}' — {subscribers} subscriber(s)")
        except Exception as exc:
            print(f"[EventPublisher] ERROR publishing to '{channel}': {exc}")
