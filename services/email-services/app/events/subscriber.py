"""
EventSubscriber — Kafka via Redpanda.

Replaces Redis Pub/Sub with a Kafka consumer.

Key differences from Redis Pub/Sub:
  - Messages are persisted to disk in Redpanda
  - If email-service is down, messages are not lost
  - The consumer resumes where it left off (offset)
  - A consumer group ensures each message is processed once

Usage in main.py:
    subscriber = EventSubscriber(
        bootstrap_servers="redpanda:9092",
        group_id="email-service-group",
        topics=["user.registered", "auth.suspicious"],
    )
    task = asyncio.create_task(subscriber.listen())
"""
import asyncio
import logging
from collections.abc import Awaitable, Callable

from aiokafka import AIOKafkaConsumer
from aiokafka.errors import KafkaError

Handler = Callable[[str], Awaitable[None]]
logger = logging.getLogger("email-service.auth")

class EventSubscriber:
    """
    Kafka consumer for email-service.

    Listens to configured topics and dispatches messages
    to handlers registered via @subscriber.on(topic).

    Automatic reconnection in the event of disconnection.
    """
    def __init__(
        self,
        bootstrap_servers: str,
        group_id: str = "email-service-group",
        client_id: str = "email-service",
    ):
        self._bootstrap_servers = bootstrap_servers
        self._group_id = group_id
        self._client_id = client_id
        self._handlers: dict[str, list[Handler]] = {}

    def on(self, topic: str):
        """
        Decorator for registering a handler on a topic.

        Usage:
            @subscriber.on("user.registered")
            async def handle_user_registered(data: str):
                ...
        """
        def decorator(func: Handler) -> Handler:
            if topic not in self._handlers:
                self._handlers[topic] = []
            self._handlers[topic].append(func)
            logger.info("kafka_handler_registered", extra={"topic": topic})
            return func
        return decorator

    async def listen(self) -> None:
        """
        Main listening loop.
        Runs indefinitely — launch using asyncio.create_task().
        Automatically reconnects upon disconnection.
        """
        topics = list(self._handlers.keys())
        if not topics:
            logger.warning("kafka_no_topics_registered")
            return

        logger.info("kafka_subscriber_starting", extra={"topics": topics})

        while True:
            consumer = None
            try:
                consumer = AIOKafkaConsumer(
                    *topics,
                    bootstrap_servers=self._bootstrap_servers,
                    group_id=self._group_id,
                    client_id=self._client_id,
                    # Read from the beginning if the group has no offset.
                    auto_offset_reset="earliest",
                    # Disable auto-commit for manual control
                    enable_auto_commit=True,
                    auto_commit_interval_ms=1000,
                    # UTF-8 deserialization
                    value_deserializer=lambda v: v.decode("utf-8"),
                    # Timeout de session
                    session_timeout_ms=30000,
                    heartbeat_interval_ms=10000,
                )

                await consumer.start()
                logger.info("kafka_consumer_started", extra={"topics": topics})

                async for message in consumer:
                    topic = message.topic
                    data = message.value

                    logger.info(
                        "kafka_message_received",
                        extra={
                            "topic": topic,
                            "partition": message.partition,
                            "offset": message.offset,
                        },
                    )

                    handlers = self._handlers.get(topic, [])
                    for handler in handlers:
                        try:
                            await handler(data)
                        except Exception as exc:
                            logger.error(
                                "kafka_handler_error",
                                extra={
                                    "topic": topic,
                                    "error": str(exc),
                                    "error_type": type(exc).__name__,
                                },
                            )

            except asyncio.CancelledError:
                logger.info("kafka_consumer_cancelled")
                break
            except KafkaError as exc:
                logger.error(
                    "kafka_connection_error",
                    extra={
                        "error": str(exc),
                        "reconnecting_in": "5s",
                    },
                )
                await asyncio.sleep(5)
            except Exception as exc:
                logger.error(
                    "kafka_unexpected_error",
                    extra={
                        "error": str(exc),
                        "reconnecting_in": "5s",
                    },
                )
                await asyncio.sleep(5)
            finally:
                if consumer:
                    try:
                        await consumer.stop()
                    except Exception:
                        pass