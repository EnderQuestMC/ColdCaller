"""
ColdCaller
https://github.com/EnderQuestMC/ColdCaller
"""

import asyncio
import os
import json
import logging
import random
from typing import BinaryIO, Optional, List, Dict, Any

import jsonschema
import discord
from discord.ext import tasks
from discord.auth import Account, CaptchaSolver


class Caller:
    def __init__(self, client: discord.Client, token: Optional[str] = None,
                 *, email: str, password: str, **kwargs) -> None:
        """
        Initializes a client. Any kwargs will be passed to the Account constructor, and indirectly the AuthClient.
        """

        self._client: discord.Client = client
        self._email: str = email
        self._password: str = password

        self._account: Account = Account(loop=self._client.loop, **kwargs)
        self._cached_token: Optional[str] = token
        self._task: Optional[asyncio.Task] = None

    @property
    def closed(self) -> bool:
        return self._task.done() if self._task is not None else True

    @property
    def client(self) -> discord.Client:
        return self._client

    @property
    def task(self) -> asyncio.Task:
        return self._task

    async def open(self) -> asyncio.Task:
        """
        Initializes the client, and logs in.
        """
        if self._cached_token is None:
            await self._account.login(self._email, self._password)
            self._cached_token = self._account.token
        await self._client.login(self._cached_token)
        self._task = self._client.loop.create_task(self._client.connect())
        return self.task

    async def close(self) -> None:
        if self.closed:
            raise RuntimeError("This caller has already been closed, or it was never opened")
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
            guilds: List[str] = None,
            avatars: List[BinaryIO] = None,
    ) -> None:
        self._closed: bool = False
        self._started: bool = False
        self._spam: str = spam
        self._loop: asyncio.AbstractEventLoop = loop
        self._usernames: List[str] = usernames
        self._guilds: List[str] = guilds
        self._avatars: List[BinaryIO] = avatars

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

    def add_caller(self, token: Optional[str] = None, *, email: str, password: str,
                   **kwargs) -> Caller:  # This is all just a little bit jank.
        """
        Adds a caller to the registry, and starts it.
        This user's email and password must already be set.
        Any kwargs will be passed to the Caller and Client constructor.
        If a token is present, it will be used over the email and password.
        """

        if self._closed:
            raise RuntimeError("The manager has had it's collections closed.")
        else:
            client: discord.Client = discord.Client(loop=loop, status=discord.Status.idle, **kwargs)

            @tasks.loop(loop=self._loop)
            async def spam() -> None:
                spammed: int = 0
                for member in client.users:
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
                            spammed += 1
                            logging.info(
                                f"Caller #{self._callers.index(self.get_caller(client))} "
                                f"spammed (and blocked) {member.name} ({member.id}), "
                                f"#{spammed} so far"
                            )
                        finally:
                            await asyncio.sleep(240)  # Said send limit.
                else:
                    await asyncio.sleep(120)

            @spam.before_loop
            async def wait_for_client() -> None:
                await client.wait_until_ready()
                await asyncio.sleep(10)

            @tasks.loop(hours=1, loop=self._loop)
            async def reidentification() -> None:
                try:
                    avatar_fp: BinaryIO = random.choice(
                        self._avatars)

                    if avatar_fp is not None:
                        avatar_fp.seek(0)  # "Rewinding a played tape"

                    avatar_bytes: bytes = avatar_fp.read() if avatar_fp is not None else None

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
                local_guilds: List[str] = self._guilds.copy()
                random.shuffle(local_guilds)
                for guild_invite in local_guilds:
                    try:
                        joinable_guild: discord.Invite = await client.fetch_invite(guild_invite)
                        joined_guild: discord.Guild = await joinable_guild.use()
                    except discord.HTTPException as http_exception:
                        if http_exception.code == 40007 and http_exception.status == 403:
                            continue  # Banned.
                        else:
                            logging.info(
                                f"Caller #{self._callers.index(self.get_caller(client))} "
                                f"couldn't use the invite {guild_invite} "
                                f"because of {http_exception.text} ({http_exception.code}, {http_exception.status})"
                            )
                    except discord.InvalidArgument or NameError:  # Whyt he hell does this raise NameError?
                        continue  # We likely just tried to join the same server.
                    except Exception:
                        raise
                    else:
                        logging.info(
                            f"Caller #{self._callers.index(self.get_caller(client))} "
                            f"joined {joined_guild.name} ({joined_guild.id})"
                        )
                    finally:
                        await asyncio.sleep(240)

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
                    try:
                        await after.user.send(self._spam)
                    except discord.HTTPException as http_exception:
                        logging.info(
                            f"Caller #{self._callers.index(self.get_caller(client))} "
                            f"couldn't spam {after.user.name} ({after.user.id}) "
                            f"because of {http_exception.text} ({http_exception.code}, {http_exception.status})"
                        )
                        raise
                    else:
                        logging.info(
                            f"Caller #{self._callers.index(self.get_caller(client))} "
                            f"spammed {after.user.name} ({after.user.id})"
                        )
                    finally:
                        await asyncio.sleep(240)  # Users can only open a limited number of DMs.
                    try:
                        await after.user.block()
                    except discord.HTTPException as http_exception:
                        logging.info(
                            f"Caller #{self._callers.index(self.get_caller(client))} "
                            f"couldn't block {after.user.name} ({after.user.id}) "
                            f"because of {http_exception.text} ({http_exception.code}, {http_exception.status})"
                        )
                        raise
                    else:
                        logging.info(
                            f"Caller #{self._callers.index(self.get_caller(client))} "
                            f"blocked {after.user.name} ({after.user.id})"
                        )
                    finally:
                        await asyncio.sleep(20)

            caller: Caller = Caller(client, token, email=email, password=password, **kwargs)

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
        if not self._started:
            raise RuntimeError("The manager has not yet started.")
        else:
            for caller in self._callers:
                await self.remove_caller(caller)

            logging.info(f"{self} closed")

            self._closed = True

    async def open(self) -> None:
        """Opens all callers."""

        if self._closed:
            raise RuntimeError("The manager has had it's collections closed.")
        if self._started:
            raise RuntimeError("The manager has started.")
        else:
            for caller in self._callers:
                await caller.open()

            logging.info(f"{self} opened")

            self._started = True


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(name)s: %(message)s")
    logging.getLogger("discord.gateway").setLevel(logging.ERROR)  # No spam in the console, pretty please?

    in_docker: bool = os.path.exists("/.dockerenv")

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

    # These are used in the Client and AuthClient constructors, the latter one being via the Account constructors.
    # This is a function so it can be different for each token.
    def get_client_assembly_kwargs(token: Dict[str, str], index: int):
        return {
            "captcha_handler": CaptchaSolver(discord.BrowserEnum.chrome, port=5000 + index) if not in_docker else None
            # In case we are in a non-interactive docker session.
        }

    for token in tokens:
        index: int = tokens.index(token)
        if token.get("token") is None:
            caller_manager.add_caller(email=token["email"], password=token["password"],
                                      **get_client_assembly_kwargs(token, index))
        else:
            caller_manager.add_caller(token["token"], email=token["email"],
                                      password=token["password"], **get_client_assembly_kwargs(token, index))

    try:
        logging.info("Running...")

        loop.run_until_complete(caller_manager.open())
        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete(caller_manager.close())
    except Exception:
        raise
