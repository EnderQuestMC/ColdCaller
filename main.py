"""
ColdCaller
https://github.com/regulad/ColdCaller
"""
import asyncio
import json
import logging
import os
from typing import Optional, List, Dict

import discord
import jsonschema
from discord.auth import Account

from coldcaller import *

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(name)s: %(message)s")
    logging.getLogger("discord.gateway").setLevel(logging.ERROR)  # No spam in the console, pretty please?

    in_docker: bool = os.path.exists("/.dockerenv")

    loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

    accounts: List[Account] = []

    # Create Folders

    if not os.path.exists("config/"):
        logging.warning("Config folder is missing!")
        os.mkdir("config/")

    if not os.path.exists("temp/"):
        os.mkdir("temp/")

    # Resources

    with open("resources/token_schema.json") as schema_fp:
        schema: dict = json.load(schema_fp)

    server_invites: Optional[str] = os.environ.get("COLDCALLER_SERVER_INVITES")

    guilds: List[str] = server_invites.split(",") if server_invites is not None else []

    if not guilds:
        with open("resources/guilds.json") as guilds_fp:
            guilds.extend(json.load(guilds_fp))

    with open("resources/words.json") as words_fp:
        words: List[str] = json.load(words_fp)

    words_username_creator: WordUsernameCreator = WordUsernameCreator(words)

    avatars: List[str] = []

    for file_name in os.listdir("resources/avatars/"):
        avatars.append(f"resources/avatars/{file_name}")

    avatar_creator: RandomFileGetter = RandomFileGetter(avatars)

    # Setup AccountCreator

    account_creator: AccountCreator = AccountCreator(
        words_username_creator,
        RandomPortCaptchaSolverCreator(discord.BrowserEnum.chrome) if not in_docker else None
        # TODO: dynamic browser enum
    )

    # Load config

    files: List[str] = []

    if not os.path.exists("config/files/"):
        logging.warning("Files folder is missing!")
        os.mkdir("config/files/")

    for file_name in os.listdir("config/files/"):
        files.append(f"config/files/{file_name}")

    with open("config/message.md") as message_fp:
        spam: str = message_fp.read()

    messsage_kwarg_creator: SpamMessageKwargCreator = SpamMessageKwargCreator(spam, files)

    # Load existing tokens

    with open("config/tokens.json") as tokens_fp:
        tokens: List[Dict[str, str]] = json.load(tokens_fp)

    with open("resources/token_schema.json") as schema_fp:
        schema: dict = json.load(schema_fp)

    jsonschema.validate(tokens, schema)

    for token in tokens:
        auth_token: Optional[str] = token.get("token")
        email: str = token["email"]
        password: str = token["password"]

        account: Account = loop.run_until_complete(
            account_creator.create_account(
                *(
                    [auth_token]
                    if auth_token is not None
                    else [email, password]
                )
            )
        )

        if auth_token is not None:
            # Some fields may never be populated.
            if account.password is None:
                account.password = password

        accounts.append(account)

    # Setup CallerManager

    caller_manager: CallerManager = CallerManager(
        messsage_kwarg_creator,
        words_username_creator,
        avatar_creator,
        guilds,
        loop=loop
    )

    for account in accounts:
        caller_manager.add_caller(account)

    # TODO: make a task to create accounts

    # Run

    try:
        logging.info("Running...")

        loop.run_until_complete(caller_manager.open())
        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete(caller_manager.close())
    except Exception:
        raise
