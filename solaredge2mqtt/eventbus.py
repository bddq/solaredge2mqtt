from __future__ import annotations

import asyncio
from typing import Callable

from solaredge2mqtt.exceptions import InvalidDataException
from solaredge2mqtt.models.base import BaseEvent
from solaredge2mqtt.logging import logger


class EventBus:
    def __init__(self) -> None:
        self._listeners: dict[str, list[Callable]] = {}
        self._subscribed_events: dict[str, type[BaseEvent]] = {}
        self._tasks: set[asyncio.Task] = set()

    def subscribe(
        self,
        event: type[BaseEvent] | list[type[BaseEvent]],
        listener: Callable,
    ) -> None:
        if isinstance(event, list):
            for _event in event:
                self.subscribe(_event, listener)
            return

        event_key = event.event_key()

        logger.info(f"Event subscribed: {event_key}")

        if event_key not in self._listeners:
            self._listeners[event_key] = []
        self._listeners[event_key].append(listener)
        self._subscribed_events[event_key] = event

    @property
    def subcribed_events(self) -> list[type[BaseEvent]]:
        return list(self._subscribed_events.values())

    def unsubscribe(self, event: type[BaseEvent], listener: Callable) -> None:
        event_key = event.event_key()
        if event_key in self._listeners:
            self._listeners[event_key].remove(listener)
            if not self._listeners[event_key]:
                self._listeners.pop(event_key, None)
                self._subscribed_events.pop(event_key, None)

    async def emit(self, event: BaseEvent) -> None:
        event_key = event.event_key()
        logger.trace(f"Event emitted: {event_key}")

        if event_key in self._listeners:
            if event.AWAIT:
                await self._notify_listeners(event, self._listeners[event_key])
            else:
                task = asyncio.create_task(
                    self._notify_listeners(event, self._listeners[event_key])
                )
                self._tasks.add(task)
                task.add_done_callback(self._tasks.remove)

    async def _notify_listeners(
        self, event: BaseEvent, listeners: list[Callable]
    ) -> None:
        await asyncio.gather(
            *[self._notify_listener(listener, event) for listener in listeners]
        )

    async def _notify_listener(self, listener: Callable, event: BaseEvent) -> None:
        try:
            await listener(event)
        except InvalidDataException as error:
            logger.warning("{message}, skipping this loop", message=error.message)

    def cancel_tasks(self):
        for task in self._tasks:
            task.cancel()
