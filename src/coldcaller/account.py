import asyncio
import logging
from typing import Dict, Any, Optional
from typing import List

from discord.auth import EmailHandler, TempMailWrapper, Account

from .creators import *

coldcaller_logger: logging.Logger = logging.getLogger(__name__)


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


__all__: List[str] = [
    "AccountCreator"
]
