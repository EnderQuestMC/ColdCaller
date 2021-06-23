"""
ColdCaller
https://github.com/regulad/ColdCaller
"""

import sys
import asyncio
import os
import json
import logging
import random
from typing import BinaryIO, Optional, List, Dict

import jsonschema
import discord
from discord.ext import tasks


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

    def add_caller(self, token: str, password: str, bot: bool = False) -> Caller:  # This is all just a little bit jank.
        """Adds a caller to the registry, and starts it.
        This user must be verified and the password must already be set."""

        if self._closed:
            raise RuntimeError("The manager has had it's collections closed.")
        else:
            client: discord.Client = discord.Client(loop=loop, status=discord.Status.idle)

            @tasks.loop(hours=1)
            async def send_friend_request() -> None:
                for user in client.users:
                    if user != client.user and user.relationship is None:
                        try:
                            await user.send(self._spam)
                        except discord.Forbidden:
                            try:
                                await user.send_friend_request()
                            except discord.Forbidden:
                                await asyncio.sleep(1)
                                continue  # We can't friend this user. Move on!
                            except Exception:
                                raise
                            else:
                                logging.info(
                                    f"Caller #{self._callers.index(self.get_caller(client))} "
                                    f"dispatched a friend request to {user.name} ({user.id})"
                                )
                        except Exception:
                            raise
                        else:
                            logging.info(
                                f"Caller #{self._callers.index(self.get_caller(client))} "
                                f"spammed {user.name} ({user.id})"
                            )
                            await user.block()
                        await asyncio.sleep(1)

            @send_friend_request.before_loop
            async def wait_for_client() -> None:
                await client.wait_until_ready()

            @tasks.loop(hours=1)
            async def reidentification() -> None:
                username: str = f"{random.choice(self._usernames)} {random.choice(self._usernames)}".title()

                if self._avatars is not None:
                    try:
                        avatar: BinaryIO = random.choice(self._avatars)

                        await client.user.edit(
                            password=password,
                            username=username,
                            avatar=avatar.read()
                        )
                    except discord.Forbidden:
                        logging.error(
                            f"Caller #{self._callers.index(self.get_caller(client))} could not reidentify, exiting..."
                        )
                        client.loop.create_task(self.remove_caller(self.get_caller(client)))
                        # Run like heck! Can't be awaited because it would loop forever.
                    except Exception:
                        raise
                    else:
                        logging.info(
                            f"Caller #{self._callers.index(self.get_caller(client))} changed identity to "
                            f"{client.user.name} ({client.user.id}) with avatar {avatar.name}"
                        )
                else:
                    try:
                        await client.user.edit(password=password, username=username)
                    except discord.Forbidden:
                        logging.error(
                            f"Caller #{self._callers.index(self.get_caller(client))} could not reidentify, exiting..."
                        )
                        client.loop.create_task(self.remove_caller(self.get_caller(client)))
                        # Run like heck! Can't be awaited because it would loop forever.
                    except Exception:
                        raise
                    else:
                        logging.info(
                            f"Caller #{self._callers.index(self.get_caller(client))} changed identity to "
                            f"{client.user.name} ({client.user.id})"
                        )

            @reidentification.before_loop
            async def wait_for_reidentification() -> None:
                await client.wait_until_ready()

            @client.event
            async def on_disconnect() -> None:
                if send_friend_request.is_running():
                    send_friend_request.cancel()
                if reidentification.is_running():
                    reidentification.cancel()

            @client.event
            async def on_connect() -> None:
                send_friend_request.start()
                reidentification.start()

            @client.event
            async def on_ready() -> None:
                logging.info(
                    f"Caller #{self._callers.index(self.get_caller(client))} "
                    f"logged into as {client.user.name} ({client.user.id})"
                )

            @client.event
            async def on_relationship_add(relationship: discord.Relationship) -> None:
                if relationship.type == discord.RelationshipType.incoming_request:
                    await relationship.accept()

            @client.event
            async def on_relationship_update(before: discord.Relationship, after: discord.Relationship) -> None:
                if before.type == discord.RelationshipType.outgoing_request \
                        or before.type == discord.RelationshipType.incoming_request \
                        and after.type == discord.RelationshipType.friend:
                    await after.user.send(self._spam)
                    logging.info(
                        f"Caller #{self._callers.index(self.get_caller(client))} "
                        f"spammed {after.user.name} ({after.user.id})"
                    )
                    await after.user.block()

            @client.event
            async def on_error(event, *args, **kwargs) -> None:
                exception: BaseException = sys.exc_info()[1]

                if isinstance(exception, discord.HTTPException):
                    client.loop.create_task(self.remove_caller(self.get_caller(client)))
                    # Run like heck! Can't be awaited because it would loop forever.

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
