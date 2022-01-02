import abc
import asyncio
import os
import random
import string
from logging import Logger
from typing import BinaryIO, Optional, List, Dict, Any

import discord
from discord.auth import *
from discord.ext import tasks

coldcaller_logger: Logger = logging.getLogger(__name__)


class Creator(abc.ABC):
    """
    A utility class to get something.
    """

    def get(self) -> Any:
        raise NotImplementedError


class KwargCreator(Creator, abc.ABC):
    def get(self) -> Dict[str, Any]:
        raise NotImplementedError


class MessageKwargCreator(abc.ABC):
    """
    A utility class for getting message kwargs
    """

    async def get(self, client: discord.Client, spamee: discord.User) -> Dict[str, Any]:
        raise NotImplementedError


class SpamMessageKwargCreator(MessageKwargCreator):
    """
    Gets the args and kwargs respectively for sending spam.
    """

    def __init__(self, message: str, filenames: Optional[List[str]] = None) -> None:
        self._message: str = message
        self._filenames: List[str] = filenames or []

    async def get(self, client: discord.Client, spamee: discord.User) -> Dict[str, Any]:
        return {
            "content"
            "files":
                [discord.File(
                    open(file, "rb"),
                    os.path.split(file)[-1]
                )
                    for file
                    in self._filenames]
        }


class BinaryIOCreator(Creator, abc.ABC):
    def get(self) -> BinaryIO:
        raise NotImplementedError


class RandomFileGetter(BinaryIOCreator):
    def __init__(self, paths: List[str]) -> None:
        self._paths = paths

    def get(self) -> BinaryIO:
        return open(random.choice(self._paths), "rb")


class IntCreator(Creator, abc.ABC):
    def get(self) -> int:
        raise NotImplementedError


class OneOfAKindIntCreator(IntCreator):
    """
    Gets a random int from a list, and keeps going until all ints on that list are exhausted.
    """

    def __init__(self, possible_ints: Optional[List[int]] = None, rollover: bool = True):
        self._possible_ints: List[int] = possible_ints if possible_ints is not None else list(range(8000, 25565))
        self._exhausted_ints: List[int] = []
        self._rollover: bool = rollover

    def release_exhausted(self) -> None:
        self._exhausted_ints.clear()

    def get(self) -> int:
        possible_copy: List[int] = self._possible_ints.copy()
        random.shuffle(possible_copy)
        for working_int in possible_copy:
            if working_int in self._exhausted_ints:
                continue
            else:
                self._exhausted_ints.append(working_int)
                return working_int
        else:
            if self._rollover:
                self.release_exhausted()
                return self.get()
            else:
                raise RuntimeError("Exhausted int supply.")


class CaptchaHandlerCreator(Creator, abc.ABC):
    def get(self) -> CaptchaHandler:
        raise NotImplementedError


class RandomPortCaptchaSolverCreator(CaptchaHandlerCreator):
    def __init__(self, browser: discord.BrowserEnum, port_creator: IntCreator = OneOfAKindIntCreator(),
                 **handler_kwargs) -> None:
        self._browser: discord.BrowserEnum = browser
        self._port_creator: IntCreator = port_creator
        self._handler_kwargs: Dict[str, Any] = handler_kwargs

    def get(self) -> CaptchaHandler:
        kwargs_copy: Dict[str, Any] = self._handler_kwargs.copy()

        if kwargs_copy.get("port") is None:
            kwargs_copy["port"] = self._port_creator.get()
        if kwargs_copy.get("browser") is None:
            kwargs_copy["browser"] = self._browser

        return CaptchaSolver(**kwargs_copy)


class StringCreator(Creator, abc.ABC):
    """
    A utility class to get things like usernames or passwords.
    """

    def get(self) -> str:
        raise NotImplementedError


class PasswordCreator(StringCreator):
    def __init__(self,
                 password_characters: List[str] = string.ascii_letters + string.digits + string.punctuation) -> None:
        self._password_characters: List[str] = password_characters

    def get(self) -> str:
        return "".join(random.choice(self._password_characters) for i in range(10))


class WordUsernameCreator(StringCreator):
    def __init__(self, username_words: List[str]) -> None:
        self._username_words: List[str] = username_words

    def get(self) -> str:
        return (
            (" " if random.randint(0, 100) > 20 else "-")
                .join(random.choice(self._username_words) for _ in range(0, random.randint(1, 2))).title()
        )


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
                            coldcaller_logger.info(
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
                        coldcaller_logger.info(
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
                        coldcaller_logger.info(
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


class AccountCreator:
    """A class that wraps the ability to create users."""

    def __init__(self, username_creator: StringCreator, handler_creator: Optional[CaptchaHandlerCreator] = None,
                 password_creator: StringCreator = PasswordCreator(), email_handler: EmailHandler = TempMailWrapper(),
                 loop: Optional[asyncio.AbstractEventLoop] = None, **extra_kwargs) -> None:
        self._username_creator: StringCreator = username_creator
        self._handler_creator: Optional[CaptchaHandlerCreator] = handler_creator
        self._password_creator: StringCreator = password_creator
        self._email_handler: EmailHandler = email_handler
        self._loop: Optional[asyncio.AbstractEventLoop] = loop
        self._extra_kwargs: Dict[str, Any] = extra_kwargs

    async def create_account(self, *args, **kwargs) -> Account:
        """
        Creates an account.
        Args will be used to log in, if any.
        Any kwargs will be passed to the account constructor.
        """

        kwargs_copy: Dict[str, Any] = self._extra_kwargs.copy()
        kwargs_copy.update(kwargs)

        if kwargs_copy.get("loop") is None and self._loop is not None:
            kwargs_copy["loop"] = self._loop

        if kwargs_copy.get("captcha_handler") is None and self._handler_creator is not None:
            kwargs_copy["captcha_handler"] = self._handler_creator.get()

        if kwargs_copy.get("email_handler") is None:
            kwargs_copy["email_handler"] = self._email_handler

        account: Account = Account(**kwargs_copy)

        if args:
            await account.login(*args)
        else:
            await account.register(self._username_creator.get(), self._password_creator.get())

        coldcaller_logger.info(
            f"Created an account with the email {account.email}, "
            f"the password {account.password}, and the token {account.token}."
        )

        return account


__all__ = [
    "Creator",
    "KwargCreator",
    "MessageKwargCreator",
    "SpamMessageKwargCreator",
    "BinaryIOCreator",
    "RandomFileGetter",
    "IntCreator",
    "OneOfAKindIntCreator",
    "CaptchaHandlerCreator",
    "RandomPortCaptchaSolverCreator",
    "StringCreator",
    "PasswordCreator",
    "WordUsernameCreator",
    "Caller",
    "CallerManager",
    "AccountCreator"
]
