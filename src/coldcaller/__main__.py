"""
ColdCaller
https://github.com/regulad/ColdCaller
"""
import asyncio
import argparse
import json
import logging
import os
from typing import Optional, List, Dict, Any

import discord
import jsonschema
from . import *
from discord.auth import Account

def spam(args: argparse.Namespace, loop: asyncio.AbstractEventLoop) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(name)s: %(message)s")
    logging.getLogger("discord.gateway").setLevel(logging.ERROR)  # No spam in the console, pretty please?

    in_docker: bool = os.path.exists("/.dockerenv")

    accounts: List[Account] = []

    # Resources

    with open(os.path.join(os.path.dirname(__file__), "resources", "token_schema.json")) as schema_fp:
        token_schema: dict = json.load(schema_fp)

    server_invites: str = args.invites

    guilds: List[str] = server_invites.split(",") if server_invites else []

    if not guilds:
        with open(os.path.join(os.path.dirname(__file__), "resources", "guilds.json")) as guilds_fp:
            guilds.extend(json.load(guilds_fp))

    with open(os.path.join(os.path.dirname(__file__), "resources", "words.json")) as words_fp:
        words: List[str] = json.load(words_fp)

    words_username_creator: WordUsernameCreator = WordUsernameCreator(words)

    avatars: List[str] = []

    for file_name in os.listdir(os.path.join(os.path.dirname(__file__), "resources", "avatars")):
        avatars.append(os.path.join(os.path.dirname(__file__), "resources", "avatars", file_name))

    avatar_creator: RandomFileGetter = RandomFileGetter(avatars)

    # Setup AccountCreator

    account_creator: AccountCreator = AccountCreator(
        words_username_creator,
        RandomPortCaptchaSolverCreator(discord.BrowserEnum[args.browser]
                                       if args.browser is not None
                                       else discord.BrowserEnum.chrome)
        if not in_docker
        else None
    )

    # Load config

    files: List[str] = []

    if not os.path.exists(os.path.join("config")):
        logging.warning("Config folder is missing!")
        os.mkdir(os.path.join("config"))

    for file_name in os.listdir(os.path.join("config")):
        files.append(os.path.join("config", "files", file_name))

    message: Optional[str] = args.message

    if not message:
        with open(os.path.join("config", "message.md")) as message_fp:
            message: str = message_fp.read()

    messsage_kwarg_creator: SpamMessageKwargCreator = SpamMessageKwargCreator(message, files)

    # Load existing tokens

    with open(os.path.join("config", "tokens.json")) as tokens_fp:
        tokens: List[Dict[str, str]] = json.load(tokens_fp)

    jsonschema.validate(tokens, token_schema)

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

    # Run

    try:
        logging.info("Running...")

        loop.run_until_complete(caller_manager.open())
        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete(caller_manager.close())
    except Exception:
        raise

def make_users(args: argparse.Namespace, loop: asyncio.AbstractEventLoop) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s:%(levelname)s:%(name)s: %(message)s")
    logging.getLogger("discord.gateway").setLevel(logging.ERROR)  # No spam in the console, pretty please?

    in_docker: bool = os.path.exists("/.dockerenv")

    amount: int = args.create

    with open(os.path.join(os.path.dirname(__file__), "resources", "words.json")) as words_fp:
        words: List[str] = json.load(words_fp)

    words_username_creator: WordUsernameCreator = WordUsernameCreator(words)

    account_creator: AccountCreator = AccountCreator(
        words_username_creator,
        RandomPortCaptchaSolverCreator(discord.BrowserEnum.chrome) if not in_docker else None
        # TODO: dynamic browser enum
    )

    accounts: List[Account] = []

    async def run():
        for index in range(amount):
            try:
                account: Account = await account_creator.create_account()
                await account.verify_email()
            except discord.DiscordException:
                continue
            except Exception:
                raise
            else:
                accounts.append(account)
            if index != amount - 1:
                await asyncio.sleep(90)

    if not os.path.exists(os.path.join("config")):
        os.mkdir(os.path.join("config"))

    loop.run_until_complete(run())

    output_json: List[Dict[str, str]] = []

    for account in accounts:
        output_json.append({
            "email": account.email,
            "password": account.password,
            "token": account.token
        })

    if os.path.exists(os.path.join("config", "tokens.json")):
        with open(os.path.join("config", "tokens.json")) as tokens_fp:
            output_json.extend(json.load(tokens_fp))

    with open(os.path.join("config", "tokens.json"), "w") as output_fp:
        json.dump(output_json, output_fp, indent=4, sort_keys=True)


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Spams discord users, and makes accounts.")
    parser.add_argument("--message", "-m", dest="message", type=str, help="The message to send.")
    parser.add_argument("--create", "-c", dest="create", type=int, help="Creates x users")
    parser.add_argument("--browser", "-b", dest="browser", type=str, help="The browser to use for the captcha. Example: chrome, edge")
    parser.add_argument("--create-only", "-o", dest="create_only", default=False, const=True, action='store_const',
                        help="Doesn't spam, only creates users.")
    parser.add_argument("--invites", "-i", dest="invites", default="", type=str, help="A comma seperated list of invites to use to join servers. Example: Oneshot,hypixel")

    args: argparse.Namespace = parser.parse_args()

    loop: asyncio.AbstractEventLoop = asyncio.get_event_loop()

    if args.create:
        make_users(args, loop)
    if not args.create_only:
        spam(args, loop)

if __name__ == "__main__":
    main()
