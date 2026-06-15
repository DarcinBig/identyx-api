import asyncio
import redis.asyncio as aioredis
from redis.asyncio.connection import SSLConnection
from typing import Awaitable, Callable

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
                # socket_timeout=None → no timeout on reading
                # socket_keepalive=True → keeps the connection alive
                client = aioredis.from_url(
                    self._redis_url,
                    encoding="utf-8",
                    decode_responses=True,
                    socket_timeout=None,            # ← fix key
                    socket_keepalive=True,          # ← maintains the connection
                    socket_connect_timeout=5.0,     # connection timeout only
                )
                async with client.pubsub() as pubsub:
                    await pubsub.subscribe(*channels)
                    print(f"[EventSubscriber] Subscribed to {channels}")

                    # Use get_message with explicit timeout
                    # instead of listen() which blocks indefinitely
                    while True:
                        try:
                            message = await pubsub.get_message(
                                ignore_subscribe_messages=True,
                                timeout=1.0,  # poll every second
                            )
                        except asyncio.CancelledError:
                            raise
                        except Exception as exc:
                            print(f"[EventSubscriber] get_message error: {exc}")
                            break

                        if message is None:
                            # No message? We'll keep waiting.
                            await asyncio.sleep(0.1)
                            continue

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
                                    f"[EventSubscriber] Handler error "
                                    f"on '{channel}': {type(exc).__name__}: {exc}"
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