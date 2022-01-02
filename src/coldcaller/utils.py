import asyncio
import logging
from typing import List, Optional

import discord
from discord.auth import Account

coldcaller_logger: logging.Logger = logging.getLogger(__name__)


async def async_test_if_account_is_in_good_standing(account: Account, *,
                                                    loop: Optional[asyncio.AbstractEventLoop] = None, **kwargs) -> bool:
    loop = loop or asyncio.get_event_loop()

    if kwargs.get("loop") is None:
        kwargs["loop"] = loop

    client: discord.Client = discord.Client(**kwargs)
    working: bool = False

    @client.event
    async def on_ready():
        try:
            if client.get_guild(256926147827335170) is not None:
                await client.leave_guild(256926147827335170)
            sample_invite: discord.Invite = await client.fetch_invite("OneShot")
            await sample_invite.use()
        except discord.HTTPException:
            working = False
            raise
        else:
            working = True
        finally:
            await client.close()

    await client.start(account.token)

    return working


def get_logging_level(name: str) -> int:
    name = name.upper()
    if name == "CRITICAL":
        return logging.CRITICAL
    elif name == "FATAL":
        return logging.FATAL
    elif name == "ERROR":
        return logging.ERROR
    elif name == "WARNING":
        return logging.WARNING
    elif name == "WARN":
        return logging.WARN
    elif name == "INFO":
        return logging.INFO
    elif name == "DEBUG":
        return logging.DEBUG
    else:
        return logging.NOTSET


async def unblock_all_as_all(accounts: List[Account], *, loop: Optional[asyncio.AbstractEventLoop], **kwargs) -> None:
    loop = loop or asyncio.get_event_loop()

    tasks: List[asyncio.Task] = []

    for account in accounts:
        tasks.append(loop.create_task(unblock_all(account, loop=loop, **kwargs)))

    for task in tasks:
        await task


async def unblock_all(account: Account, *, loop: Optional[asyncio.AbstractEventLoop], **kwargs) -> None:
    loop = loop or asyncio.get_event_loop()

    if kwargs.get("loop") is None:
        kwargs["loop"] = loop

    client: discord.Client = discord.Client(**kwargs)

    @client.event
    async def on_ready():
        for user in client.users:
            if user is client.user:
                continue
            user: discord.User
            if user.is_blocked():
                try:
                    await user.unblock()
                except discord.HTTPException:
                    coldcaller_logger.warning(
                        f"Couldn't unblock {user.name}#{user.discriminator} ({user.id}) as "
                        f"{client.user.name}#{client.user.discriminator} ({client.user.id})"
                    )
                    continue
                except Exception:
                    raise
                else:
                    coldcaller_logger.info(
                        f"Unblocked {user.name}#{user.discriminator} ({user.id}) as "
                        f"{client.user.name}#{client.user.discriminator} ({client.user.id})"
                    )
                finally:
                    await asyncio.sleep(10)

    await client.start(account.token)


__all__: List[str] = [
    "unblock_all_as_all",
    "unblock_all",
    "async_test_if_account_is_in_good_standing",
    "get_logging_level"
]
