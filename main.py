"""
ColdCaller
https://github.com/regulad/ColdCaller
"""

import asyncio
import os
import json
import logging
import random
from typing import BinaryIO, Optional, List, Dict

import jsonschema
import discord


class Caller:
    def __init__(self, client: discord.Client, token: str, bot: bool = False) -> None:
        """Schedules a caller's execution."""

        self._client: discord.Client = client
        self._token: str = token
        self._task: asyncio.Task = client.loop.create_task(client.start(token, bot=bot))

    @property
    def closed(self) -> bool:
        return self._client.is_closed() or self._task.done()

    @property
    def client(self) -> discord.Client:
        return self._client

    @property
    def token(self) -> str:
        return self._token

    @property
    def task(self) -> asyncio.Task:
        return self._task

    async def close(self) -> None:
        if self.closed:
            raise RuntimeError("This caller has already been closed.")
        else:
            if not self._client.is_closed():
                await self._client.close()
            if not self._task.done():
                await self._task


class CallerManager:
    """Class that manages callers."""

    def __init__(
            self,
            spam: str,
            loop: asyncio.AbstractEventLoop,
            usernames: List[str],
            avatars: Optional[List[BinaryIO]] = None,
    ) -> None:
        self._closed: bool = False
        self._spam: str = spam
        self._loop: asyncio.AbstractEventLoop = loop
        self._usernames: List[str] = usernames
        self._avatars: Optional[List[BinaryIO]] = avatars

        self._callers: List[Caller] = []

    def get_caller(self, client: discord.Client) -> Optional[Caller]:
        """Gets a caller from it's client."""

        if self._closed:
            raise RuntimeError("The manager has had it's collections closed.")
        else:
            for caller in self._callers:
                if caller.client == client:
                    return caller
            else:
                raise ValueError("Client does not have a caller.")

    def add_caller(self, token: str, password: str, bot: bool = False) -> Caller:
        """Adds a caller to the registry, and starts it.
        This user must be verified and the password must already be set."""

        if self._closed:
            raise RuntimeError("The manager has had it's collections closed.")
        else:
            client: discord.Client = discord.Client(loop=loop)

            @client.event
            async def on_ready() -> None:
                logging.info(
                    f"Caller #{self._callers.index(self.get_caller(client))} logged into as "
                    f"{client.user.name} ({client.user.id})"
                )

                username: str = f"{random.choice(self._usernames)} {random.choice(self._usernames)}".title()

                if self._avatars is not None:
                    await client.user.edit(
                        password=password,
                        username=username,
                        avatar=random.choice(self._avatars).read()
                    )
                else:
                    await client.user.edit(password=password, username=username)

                logging.info(
                    f"Caller #{self._callers.index(self.get_caller(client))} changed identity to "
                    f"{client.user.name} ({client.user.id})"
                )

            @client.event
            async def on_relationship_update(before: discord.Relationship, after: discord.Relationship) -> None:
                if before.type == discord.RelationshipType.outgoing_request \
                        and after.type == discord.RelationshipType.friend:
                    await after.user.send(self._spam)
                    logging.info(
                        f"Caller #{self._callers.index(self.get_caller(client))} spammed "
                        f"{after.user.name} ({after.user.id})"
                    )

            caller: Caller = Caller(client, token, bot)

            self._callers.append(caller)

            logging.info(f"Caller added at {self._callers.index(self.get_caller(client)) + 1}")

            return caller

    async def remove_caller(self, caller: Caller) -> None:
        if self._closed:
            raise RuntimeError("The manager has had it's collections closed.")
        else:
            await caller.close()

            logging.info(
                f"Caller #{self._callers.index(caller)} closed."
            )

            del self._callers[self._callers.index(caller)]

    async def close(self) -> None:
        """Closes all the callers."""

        if self._closed:
            raise RuntimeError("The manager has had it's collections closed.")
        else:
            for caller in self._callers:
                await self.remove_caller(caller)

            logging.info(
                f"{self.__class__.__name__} closed"
            )

            self._closed = True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(name)s: %(message)s")

    if not os.path.exists("config/"):
        logging.warning("Config folder is missing!")
        os.mkdir("config/")

    with open("config/message.md") as message_fp:
        spam: str = message_fp.read()

    with open("config/tokens.json") as tokens_fp:
        tokens: List[Dict[str, str]] = json.load(tokens_fp)

    with open("resources/token_schema.json") as schema_fp:
        schema: dict = json.load(schema_fp)

    with open("resources/words.json") as words_fp:
        words: List[str] = json.load(words_fp)

    avatars: List[BinaryIO] = []

    for file_name in os.listdir("resources/avatars/"):
        avatars.append(open(f"resources/avatars/{file_name}", "rb"))

    jsonschema.validate(tokens, schema)

    loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

    caller_manager: CallerManager = CallerManager(spam, loop, words, avatars)

    for token in tokens:
        caller_manager.add_caller(token["token"], token["password"])

    try:
        logging.info(
            "Running..."
        )

        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete(caller_manager.close())
    except Exception:
        raise
