import asyncio
import logging
from typing import List

import discord
from discord.auth import Account


def test_if_account_is_in_good_standing(account: Account, *, loop: asyncio.AbstractEventLoop = None, **kwargs) -> bool:
    loop = loop or asyncio.get_event_loop()
    return loop.run_until_complete(async_test_if_account_is_in_good_standing(account, loop=loop, **kwargs))


async def async_test_if_account_is_in_good_standing(account: Account, *, loop: asyncio.AbstractEventLoop = None,
                                                    **kwargs) -> bool:
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


__all__: List[str] = [
    "test_if_account_is_in_good_standing",
    "async_test_if_account_is_in_good_standing",
    "get_logging_level"
]
