import abc
import os
import random
import string
from typing import Any, Dict, Optional, List, BinaryIO

import discord
from discord.auth import CaptchaHandler, CaptchaSolver


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
            "content": self._message,
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


__all__: List[str] = [
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
    "WordUsernameCreator"
]
