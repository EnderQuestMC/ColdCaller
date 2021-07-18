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
        return self._task.done()

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
            guilds: Optional[List[str]] = None,
            avatars: Optional[List[BinaryIO]] = None,
    ) -> None:
        self._closed: bool = False
        self._spam: str = spam
        self._loop: asyncio.AbstractEventLoop = loop
        self._usernames: List[str] = usernames
        self._guilds: Optional[List[str]] = guilds
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
                return None

    def add_caller(self, token: str, password: str) -> Caller:  # This is all just a little bit jank.
        """Adds a caller to the registry, and starts it.
        This user must be verified and the password must already be set."""

        if self._closed:
            raise RuntimeError("The manager has had it's collections closed.")
        else:
            client: discord.Client = discord.Client(loop=loop, status=discord.Status.idle)

            @tasks.loop(loop=self._loop)
            async def spam() -> None:
                for member in client.users:
                # async for guild in client.fetch_guilds():
                #     await asyncio.sleep(5)
                #     for member in guild.members:  # guild.members is broken
                        if member != client.user \
                                and not member.bot \
                                and (member.relationship is None
                                     or member.relationship.type is not discord.RelationshipType.blocked):
                            try:
                                await member.send(self._spam)
                            except discord.Forbidden:
                                try:
                                    await asyncio.sleep(10)
                                    await member.send_friend_request()
                                except discord.HTTPException:
                                    pass
                                except Exception:
                                    raise
                                else:
                                    logging.info(
                                        f"Caller #{self._callers.index(self.get_caller(client))} "
                                        f"dispatched a friend request to {member.name} ({member.id})"
                                    )
                                finally:
                                    await asyncio.sleep(20)
                            except Exception:
                                raise
                            else:
                                await member.block()
                                logging.info(
                                    f"Caller #{self._callers.index(self.get_caller(client))} "
                                    f"spammed (and blocked) {member.name} ({member.id})"
                                )
                            finally:
                                await asyncio.sleep(40)
                else:
                    await asyncio.sleep(120)

            @spam.before_loop
            async def wait_for_client() -> None:
                await client.wait_until_ready()
                await asyncio.sleep(10)

            @tasks.loop(hours=1, loop=self._loop)
            async def reidentification() -> None:
                try:
                    avatar_fp: Optional[BinaryIO] = random.choice(self._avatars) if self._avatars is not None else None
                    avatar_bytes: Optional[bytes] = avatar_fp.read() if avatar_fp is not None else None

                    if avatar_bytes is not None:
                        avatar_fp.seek(0)

                    await client.user.edit(
                        password=password,
                        username=(
                            (" " if random.randint(0, 100) > 20 else "-")
                            .join(random.choice(self._usernames) for _ in range(0, random.randint(1, 2))).title()
                        ),
                        avatar=avatar_bytes,
                        house=random.choice(list(discord.HypeSquadHouse))
                    )
                except discord.HTTPException:
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
                finally:
                    await asyncio.sleep(30)

            @reidentification.before_loop
            async def wait_for_reidentification() -> None:
                await client.wait_until_ready()
                await asyncio.sleep(30)

            @tasks.loop(minutes=40, loop=self._loop)
            async def join_guilds() -> None:
                random.shuffle(self._guilds)  # Just because we aren't random.choicing it
                for guild_invite in self._guilds:
                    try:
                        joined_guild: discord.Guild = await client.join_guild(guild_invite)
                    except discord.HTTPException as httpException:
                        logging.info(
                            f"Caller #{self._callers.index(self.get_caller(client))} "
                            f"couldn't use the invite {guild_invite} "
                            f"because of {httpException.text} ({httpException.code}, {httpException.status})"
                        )
                    except discord.InvalidArgument:
                        continue  # We likely just tried to join the same server. Pass it on!
                    except Exception:
                        raise
                    else:
                        logging.info(
                            f"Caller #{self._callers.index(self.get_caller(client))} "
                            f"joined {joined_guild.name} ({joined_guild.id})"
                        )
                    finally:
                        await asyncio.sleep(120)

            @join_guilds.before_loop
            async def wait_for_guilds() -> None:
                await client.wait_until_ready()
                await asyncio.sleep(20)

            @client.event
            async def on_disconnect() -> None:
                if spam.is_running():
                    spam.cancel()
                if reidentification.is_running():
                    reidentification.cancel()
                if join_guilds.is_running():
                    join_guilds.cancel()

            @client.event
            async def on_connect() -> None:
                spam.start()
                reidentification.start()
                join_guilds.start()

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

    with open("resources/guilds.json") as guilds_fp:
        guilds: List[str] = json.load(guilds_fp)

    with open("resources/words.json") as words_fp:
        words: List[str] = json.load(words_fp)

    avatars: List[BinaryIO] = []

    for file_name in os.listdir("resources/avatars/"):
        avatars.append(open(f"resources/avatars/{file_name}", "rb"))

    jsonschema.validate(tokens, schema)

    loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

    caller_manager: CallerManager = CallerManager(spam, loop, words, guilds, avatars)

    for token in tokens:
        caller_manager.add_caller(token["token"], token["password"])

    try:
        logging.info("Running...")

        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete(caller_manager.close())
    except Exception:
        raise
