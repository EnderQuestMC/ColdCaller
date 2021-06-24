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
from discord.ext import tasks


class Caller:
    def __init__(self, client: discord.Client, token: str) -> None:
        """Schedules a caller's execution."""

        self._client: discord.Client = client
        self._token: str = token
        self._task: asyncio.Task = client.loop.create_task(client.start(token))

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

    def add_caller(self, token: str, password: str) -> Caller:  # This is all just a little bit jank.
        """Adds a caller to the registry, and starts it.
        This user must be verified and the password must already be set."""

        if self._closed:
            raise RuntimeError("The manager has had it's collections closed.")
        else:
            client: discord.Client = discord.Client(loop=loop, status=discord.Status.idle)

            @tasks.loop(minutes=30)
            async def spam() -> None:
                for user in client.users:  # Only thing that kinda works. Need to make members work
                    if user != client.user:
                        profile: discord.Profile = await client.fetch_user_profile(user.id)
                        user: discord.User = profile.user
                        await asyncio.sleep(1)  # Should wait after every API request, because self-bot shenanigans.
                        if user.relationship is None:
                            try:
                                await user.send(self._spam)
                            except discord.Forbidden:
                                await asyncio.sleep(1)
                                try:
                                    await user.send_friend_request()
                                except discord.Forbidden:
                                    await asyncio.sleep(1)
                                    continue
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
                                await asyncio.sleep(1)
                                await user.block()
                                await asyncio.sleep(1)
                                logging.info(
                                    f"Caller #{self._callers.index(self.get_caller(client))} "
                                    f"spammed {user.name} ({user.id})"
                                )

            @spam.before_loop
            async def wait_for_client() -> None:
                await client.wait_until_ready()

            """
            @tasks.loop(hours=1)
            async def reidentification() -> None:
                try:
                    await client.user.edit(
                        password=password,
                        username=(
                            (" " if random.randint(0, 100) > 20 else "-")
                            .join(random.choice(self._usernames) for _ in range(0, random.randint(1, 2))).title()
                        ),
                        avatar=random.choice(self._avatars).read() if self._avatars is not None else None,
                        house=random.choice(discord.HypeSquadHouse.__members__.values())
                    )
                except discord.Forbidden:
                    logging.warning(
                        f"Caller #{self._callers.index(self.get_caller(client))} could not reidentify!"
                    )
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
            """

            @client.event
            async def on_disconnect() -> None:
                if spam.is_running():
                    spam.cancel()
                # if reidentification.is_running():
                #     reidentification.cancel()

            @client.event
            async def on_connect() -> None:
                spam.start()
                # reidentification.start()

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
                    await after.user.block()
                    logging.info(
                        f"Caller #{self._callers.index(self.get_caller(client))} "
                        f"spammed {after.user.name} ({after.user.id})"
                    )

            caller: Caller = Caller(client, token)

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
