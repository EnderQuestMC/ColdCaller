import asyncio
import logging
import random
from typing import List, BinaryIO
from typing import Optional

import discord
from discord.auth import Account
from discord.ext import tasks

from .creators import *

coldcaller_logger: logging.Logger = logging.getLogger(__name__)


class Caller:
    def __init__(self, client: discord.Client, account: Account,
                 loop: Optional[asyncio.AbstractEventLoop] = None, **kwargs) -> None:
        """
        Initializes a client. Any kwargs will be passed to the Account constructor, and indirectly the AuthClient.
        """

        self._client: discord.Client = client
        self._account: Account = account
        self._task: Optional[asyncio.Task] = None
        self._loop: asyncio.AbstractEventLoop = loop or self._client.loop

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
        await self._client.login(self._account.token)
        self._task = self._loop.create_task(self._client.connect())
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
            spam: MessageKwargCreator,
            usernames: StringCreator,
            avatars: Optional[BinaryIOCreator] = None,
            guilds: List[str] = None,
            *,
            loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._closed: bool = False
        self._started: bool = False
        self._spam: MessageKwargCreator = spam
        self._loop: asyncio.AbstractEventLoop = loop
        self._usernames: StringCreator = usernames
        self._avatars: Optional[BinaryIOCreator] = avatars
        self._guilds: List[str] = guilds

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

    def add_caller(self, account: Account, client: Optional[discord.Client] = None, **kwargs) -> Caller:
        """
        Adds a caller to the registry, and starts it.
        This user's email and password must already be set.
        Any kwargs will be passed to the Caller and Client constructor.
        If a token is present, it will be used over the email and password.
        """

        if self._closed:
            raise RuntimeError("The manager has had it's collections closed.")
        else:
            if kwargs.get("loop") is None:
                kwargs["loop"] = self._loop
            if kwargs.get("status") is None:
                kwargs["status"] = random.choice(list(discord.Status))

            client: discord.Client = client or discord.Client(**kwargs)

            @tasks.loop(loop=self._loop)
            async def spam() -> None:
                spammed: int = 0
                for member in client.users:
                    if member != client.user \
                            and not member.bot \
                            and (member.relationship is None
                                 or member.relationship.type is not discord.RelationshipType.blocked):
                        try:
                            await member.send(**await self._spam.get(client, member))
                        except discord.Forbidden:
                            try:
                                await asyncio.sleep(10)
                                await member.send_friend_request()
                            except discord.HTTPException:
                                pass
                            except Exception:
                                raise
                            else:
                                coldcaller_logger.info(
                                    f"Caller #{self._callers.index(self.get_caller(client)) + 1} "
                                    f"dispatched a friend request to {member.name} ({member.id})"
                                )
                            finally:
                                await asyncio.sleep(20)
                        except Exception:
                            raise
                        else:
                            await member.block()
                            spammed += 1
                            coldcaller_logger.info(
                                f"Caller #{self._callers.index(self.get_caller(client)) + 1} "
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
                    avatar_fp: Optional[BinaryIO] = self._avatars.get() if self._avatars is not None else None

                    if avatar_fp is not None:
                        avatar_fp.seek(0)  # "Rewinding a played tape"

                    avatar_bytes: bytes = avatar_fp.read() if avatar_fp is not None else None

                    await client.user.edit(
                        password=account.password,
                        username=self._usernames.get(),
                        avatar=avatar_bytes,
                        house=random.choice(list(discord.HypeSquadHouse))
                    )
                except discord.HTTPException:
                    coldcaller_logger.warning(
                        f"Caller #{self._callers.index(self.get_caller(client)) + 1} could not reidentify!"
                    )
                except Exception:
                    raise
                else:
                    coldcaller_logger.info(
                        f"Caller #{self._callers.index(self.get_caller(client)) + 1} changed identity to "
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
                            coldcaller_logger.warning(
                                f"Caller #{self._callers.index(self.get_caller(client)) + 1} "
                                f"couldn't use the invite {guild_invite} "
                                f"because of {http_exception.text} ({http_exception.code}, {http_exception.status})"
                            )
                    except discord.InvalidArgument or NameError:  # Why the hell does this raise NameError?
                        continue  # We likely just tried to join the same server.
                    except Exception:
                        raise
                    else:
                        coldcaller_logger.info(
                            f"Caller #{self._callers.index(self.get_caller(client)) + 1} "
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
                coldcaller_logger.info(
                    f"Caller #{self._callers.index(self.get_caller(client)) + 1} "
                    f"logged in as {client.user.name} ({client.user.id})"
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
                        await after.user.send(**await self._spam.get(client, after.user))
                    except discord.HTTPException as http_exception:
                        coldcaller_logger.warning(
                            f"Caller #{self._callers.index(self.get_caller(client)) + 1} "
                            f"couldn't spam {after.user.name} ({after.user.id}) "
                            f"because of {http_exception.text} ({http_exception.code}, {http_exception.status})"
                        )
                        raise
                    except Exception as exception:
                        raise exception
                    else:
                        coldcaller_logger.info(
                            f"Caller #{self._callers.index(self.get_caller(client)) + 1} "
                            f"spammed {after.user.name} ({after.user.id})"
                        )
                    finally:
                        await asyncio.sleep(240)  # Users can only open a limited number of DMs.
                    try:
                        await after.user.block()
                    except discord.HTTPException as http_exception:
                        coldcaller_logger.warning(
                            f"Caller #{self._callers.index(self.get_caller(client)) + 1} "
                            f"couldn't block {after.user.name} ({after.user.id}) "
                            f"because of {http_exception.text} ({http_exception.code}, {http_exception.status})"
                        )
                        raise
                    else:
                        coldcaller_logger.info(
                            f"Caller #{self._callers.index(self.get_caller(client)) + 1} "
                            f"blocked {after.user.name} ({after.user.id})"
                        )
                    finally:
                        await asyncio.sleep(20)

            caller: Caller = Caller(client, account, **kwargs)

            self._callers.append(caller)

            coldcaller_logger.info(f"Caller added at {self._callers.index(self.get_caller(client)) + 1}")

            return caller

    async def remove_caller(self, caller: Caller) -> None:
        if self._closed:
            raise RuntimeError("The manager has had it's collections closed.")
        else:
            await caller.close()

            coldcaller_logger.info(
                f"Caller #{self._callers.index(caller) + 1} closed."
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

            coldcaller_logger.info(f"{self} closed")

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

            coldcaller_logger.info(f"{self} opened")

            self._started = True


__all__: List[str] = [
    "Caller",
    "CallerManager"
]
