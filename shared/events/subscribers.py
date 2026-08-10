"""
Subscriber Redis Pub/Sub.

Copy this file to app/events/subscriber.py of each service
which consumes events.

Usage:
    subscriber = EventSubscriber(redis_url="redis://localhost:6379/1")

    @subscriber.on(CHANNEL_USER_REGISTERED)
    async def handle_user_registered(data: str):
        event = UserRegisteredEvent.from_json(data)
        await email_service.send_verification_email(...)

    # In lifespan:
    asyncio.create_task(subscriber.listen())
"""
import asyncio
from collections.abc import Awaitable, Callable

import redis.asyncio as aioredis

Handler = Callable[[str], Awaitable[None]]

class EventSubscriber:
    """
    Listens to Redis Pub/Sub channels and dispatches messages
    to registered handlers.

    Runs in the background via asyncio.create_task().
    Automatically reconnects in case of an error.
    """
    def __init__(self, redis_url: str):
        self._redis_url = redis_url
        self._handlers: dict[str, list[Handler]] = {}

    def on(self, channel: str):
        """
        Decorator for registering a handler on a channel.

        Usage:

            @subscriber.on("user.registered")
            async def handle(data: str):
                ...
        """
        def decorator(func: Handler) -> Handler:
            if channel not in self._handlers:
                self._handlers[channel] = []
            self._handlers[channel].append(func)
            print(f"[EventSubscriber] Handler registered for '{channel}'")
            return func
        return decorator

    async def listen(self) -> None:
        """
        Main listening loop.
        Runs indefinitely — start with `asyncio.create_task()`.
        Reconnects automatically upon disconnection.
        """
        channels = list(self._handlers.keys())
        if not channels:
            print("[EventSubscriber] No channels to listen to.")
            return

        print(f"[EventSubscriber] Listening on: {channels}")

        while True:
            try:
                client = aioredis.from_url(
                    self._redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                )
                async with client.pubsub() as pubsub:
                    await pubsub.subscribe(*channels)
                    print(f"[EventSubscriber] Subscribed to {channels}")

                    async for message in pubsub.listen():
                        if message["type"] != "message":
                            continue

                        channel = message["channel"]
                        data = message["data"]

                        handlers = self._handlers.get(channel, [])
                        for handler in handlers:
                            try:
                                await handler(data)
                            except Exception as exc:
                                print(
                                    f"[EventSubscriber] Handler error on '{channel}': "
                                    f"{type(exc).__name__}: {exc}"
                                )

            except asyncio.CancelledError:
                print("[EventSubscriber] Listener cancelled.")
                break
            except Exception as exc:
                print(
                    f"[EventSubscriber] Connection lost: {exc}. "
                    f"Reconnecting in 5s..."
                )
                await asyncio.sleep(5)