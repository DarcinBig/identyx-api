"""
EventPublisher — Kafka via Redpanda.

Replaces Redis Pub/Sub with Kafka for message persistence.
Every message is guaranteed to be written to the topic, even if
the consumer (email-service) is temporarily unavailable.

Topics used:
    user.registered      → verification email
    auth.login           → analytics / audit (future versions)
    auth.suspicious      → post-brute-force security email
    user.deleted         → data cleanup (future versions)
"""
import logging

from aiokafka import AIOKafkaProducer
from aiokafka.errors import KafkaError

logger = logging.getLogger("auth-service.events")


class EventPublisher:
    """
    Publishes events to Kafka topics via Redpanda.

    Usage in main.py:
        publisher = EventPublisher(bootstrap_servers="redpanda:9092")
        await publisher.connect()
        await publisher.publish("user.registered", event)
        await publisher.close()
    """
    def __init__(
            self,
            bootstrap_servers: str,
            client_id: str = "auth-service"
    ):
        self._bootstrap_servers = bootstrap_servers
        self._client_id = client_id
        self._producer:  AIOKafkaProducer | None = None

    async def connect(self) -> None:
        """
        Initializes the Kafka producer.
        Called within the FastAPI lifespan.
        """
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self._bootstrap_servers,
            client_id=self._client_id,
            # UTF-8 serialization of values
            value_serializer=lambda value: value.encode("utf-8"),
            # Wait for confirmation of the 'write' to the leader
            acks="all",
            # Automatic retry in the event of a transient error
            retry_backoff_ms=200,
            request_timeout_ms=10000,
        )
        await self._producer.start()
        logger.info("kafka_producer_connected", extra={"bootstrap_servers": self._bootstrap_servers})

    async def close(self) -> None:
        """Cleanly closes the producer"""
        if self._producer:
            await self._producer.stop()
            self._producer = None
            logger.info("kafka_producer_closed")

    # async def check_connection(self) -> bool:
    #     if not self._client:
    #         return False
    #     try:
    #         await self._client.ping()
    #         return True
    #     except Exception:
    #         return False

    async def publish(self, topic: str, event) -> None:
        """
        Publishes an event to a Kafka topic.

        Args:
            topic: topic name (e.g., "user.registered")
            event: instance of an event dataclass with a .to_json() method

        "Fire-and-forget" at the application level —
        errors are logged but do not crash the service.
        Kafka persistence guarantees delivery to the consumer.
        """
        if not  self._producer:
            logger.warning("kafka_producer_not_connected", extra={
                "topic": topic,
                "event_lost": True
            })
            return

        try:
            payload = event.to_json()
            await self._producer.send_and_wait(topic, payload)
            logger.info("kafka_event_published", extra={
                "topic": topic,
                "payload_size": len(payload),
            })
        except KafkaError as exc:
            logger.error("kafka_publish_error", extra={
                "topic": topic,
                "error": str(exc),
            })
        except Exception as exc:
            logger.error("kafka_publish_unexpected_error", extra={
                "topic": topic,
                "error": str(exc),
            })