"""
ColdCaller
https://github.com/regulad/ColdCaller
"""
import argparse
import asyncio
import datetime
import json
import logging
import os
from typing import Optional, List, Dict, Any

import discord
import dislog
import jsonschema
from discord.auth import Account

from . import *


coldcaller_logger: logging.Logger = logging.getLogger(__name__)


def main() -> None:
    # Parser TODO: Add better docker support

    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Spams discord users, and makes accounts.")
    parser.add_argument("--message", "-m", dest="message", type=str, help="The message to send.")
    parser.add_argument("--create", "-c", dest="create", type=int, help="Creates x users")
    parser.add_argument("--browser", "-b", dest="browser", type=str, help="The browser to use for the captcha. "
                                                                          "Example: chrome, edge")
    parser.add_argument("--no-spam", "-o", dest="no_spam", default=False, const=True, action='store_const',
                        help="Doesn't scam any users, only does the other tasks.")
    parser.add_argument("--save", "-s", dest="save_users", default=False, const=True, action='store_const',
                        help="If the accounts created should be saved into the configuration, "
                             "or if they should be saved into a new file.")
    parser.add_argument("--invites", "-i", dest="invites", default="", type=str,
                        help="A comma seperated list of invites to use to join servers. Example: Oneshot,hypixel")
    parser.add_argument("--loglevel", "-l", dest="loglevel", default="INFO",
                        help="Sets the log level, Example: error, info, debug")
    parser.add_argument("--proxy", "-p", dest="proxy",
                        help="Adds a proxy in the format of "
                             "http://your_user:your_password@your_proxy_url:your_proxy_port")
    parser.add_argument("--unblock", "-u", dest="unblock", default=False, const=True, action='store_const',
                        help="Unblocks all accounts as all users.")
    parser.add_argument("--verify", "-v", dest="verify", default=False, const=True, action='store_const',
                        help="Verifies all accounts are in good standing.")
    parser.add_argument("--clean", "-g", dest="clean", default=False, const=True, action='store_const',
                        help="Verifies all accounts are in good standing, and snips out those that arent. "
                             "Take a copy of your tokens before running this, it may have false negatives.")
    parser.add_argument("--leave", "-e", dest="leave", default=False, const=True, action='store_const',
                        help="Leaves/exits all guilds.")
    parser.add_argument("--no-reidentify", "-r", dest="reidentify", default=False, const=True, action='store_const',
                        help="Does not reidentify the spammers.")
    parser.add_argument("--no-join", "-j", dest="join", default=False, const=True, action='store_const',
                        help="Does not join any new guilds.")
    parser.add_argument("--webhook", "-w", dest="webhook", help="A webhook url to log to.")
    parser.add_argument("--test-user", "-t", dest="test_user", type=int,
                        help="The id of a user to spam, instead of the normal process.")

    args: argparse.Namespace = parser.parse_args()

    constructor_kwargs: Dict[str, Any] = {
        "proxy": args.proxy
    }

    # Common

    loop: asyncio.AbstractEventLoop = asyncio.get_event_loop_policy().get_event_loop()

    logging.basicConfig(level=get_logging_level(args.loglevel),
                        format="%(asctime)s:%(levelname)s:%(name)s: %(message)s")
    logging.getLogger("discord.gateway").setLevel(logging.ERROR)  # No spam in the console, pretty please?

    if args.webhook:
        logging.root.addHandler(dislog.DiscordWebhookHandler(args.webhook))

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
        else None,
        **constructor_kwargs
    )

    # Load config

    files: List[str] = []
    embeds: List[dict] = []

    if not os.path.exists(os.path.join("config")):
        coldcaller_logger.warning("Config folder is missing!")
        os.mkdir(os.path.join("config"))

    if not os.path.exists(os.path.join("config", "files")):
        os.mkdir(os.path.join("config", "files"))

    for file_name in os.listdir(os.path.join("config", "files")):
        files.append(os.path.join("config", "files", file_name))

    message: Optional[str] = args.message

    if not message:
        with open(os.path.join("config", "message.md")) as message_fp:
            message: str = message_fp.read()

    embed: Optional[dict] = None

    if os.path.exists(os.path.join("config", "embed.json")):
        with open(os.path.join("config", "embed.json")) as embed_fp:
            embed = json.load(embed_fp)

    messsage_kwarg_creator: SpamMessageKwargCreator = SpamMessageKwargCreator(message, files, embed)

    # Load existing tokens

    with open(os.path.join("config", "tokens.json")) as tokens_fp:
        tokens: List[Dict[str, str]] = json.load(tokens_fp)

    jsonschema.validate(tokens, token_schema)

    account_tasks: List[asyncio.Task] = []

    async def load_account(account_creator_coro) -> None:
        account: Account = await account_creator_coro

        if auth_token is not None:
            # Some fields may never be populated.
            if account.password is None:
                account.password = password

        accounts.append(account)

    for token in tokens:
        auth_token: Optional[str] = token.get("token")
        email: str = token["email"]
        password: str = token["password"]

        account_task: asyncio.Task = loop.create_task(
            load_account(
                account_creator.create_account(
                    *(
                        [auth_token]
                        if auth_token is not None
                        else [email, password]
                    )
                )
            )
        )

        account_tasks.append(account_task)

    for account_task in account_tasks:
        loop.run_until_complete(account_task)  # This can possibly be done better

    # Branching

    if args.unblock:
        loop.run_until_complete(unblock_all_as_all(accounts.copy(), loop=loop, **constructor_kwargs))

    if args.verify:
        loop.run_until_complete(verify_all(accounts.copy(), loop=loop, **constructor_kwargs))

    if args.clean:
        good_accounts: List[Account] = loop.run_until_complete(verify_all(accounts.copy(), loop=loop,
                                                                          **constructor_kwargs))

        output_json: List[Dict[str, str]] = []

        for account in good_accounts:
            output_json.append({
                "email": account.email,
                "password": account.password,
                "token": account.token
            })

        with open(os.path.join("config", "tokens.json"), "w") as output_fp:
            json.dump(output_json, output_fp, indent=4, sort_keys=True)

        accounts.clear()
        accounts.extend(good_accounts)

    if args.leave:
        loop.run_until_complete(leave_all_as_all(accounts.copy(), loop=loop, **constructor_kwargs))

    if args.create:
        amount: int = args.create

        new_accounts: List[Account] = []

        async def run():
            for index in range(amount):
                try:
                    account: Account = await account_creator.create_account()
                    await account.verify_email()
                except discord.DiscordException:
                    coldcaller_logger.error("Cannot make account!")
                    raise
                except RuntimeError as runtime_error:
                    if str(runtime_error) == "Retry":
                        coldcaller_logger.error("Cannot verify email!")
                    raise
                except Exception:
                    raise
                else:
                    if await verify_account(account, loop=loop):
                        new_accounts.append(account)
                    else:
                        raise RuntimeError("Account is not in good standing!")
                if index != amount - 1:  # Don't bother if we are about to do something else
                    await asyncio.sleep(90)

        loop.run_until_complete(run())

        if args.save_users:
            intermediate = []
            intermediate.extend(accounts)
            intermediate.extend(new_accounts)

            output_json: List[Dict[str, str]] = []

            for account in intermediate:
                output_json.append({
                    "email": account.email,
                    "password": account.password,
                    "token": account.token
                })

            with open(os.path.join("config", "tokens.json"), "w") as output_fp:
                json.dump(output_json, output_fp, indent=4, sort_keys=True)
        elif not os.path.exists(os.path.join("output")):
            os.mkdir(os.path.join("output"))

            output_json: List[Dict[str, str]] = []

            for account in new_accounts:
                output_json.append({
                    "email": account.email,
                    "password": account.password,
                    "token": account.token
                })

            with open(os.path.join("output", f"{datetime.datetime.now().isoformat()}.json"), "w") as output_fp:
                json.dump(output_json, output_fp, indent=4, sort_keys=True)

    if not args.no_spam:
        # Setup CallerManager

        caller_manager: CallerManager = CallerManager(
            messsage_kwarg_creator,
            words_username_creator,
            avatar_creator,
            guilds if not args.join else [],
            not args.reidentify,
            args.test_user if args.test_user else None,
            loop=loop
        )

        for account in accounts:
            caller_manager.add_caller(account, **constructor_kwargs)

        # Run

        try:
            coldcaller_logger.info("Running...")

            loop.run_until_complete(caller_manager.open())
            loop.run_forever()
        except KeyboardInterrupt:
            loop.run_until_complete(caller_manager.close())

            coldcaller_logger.info("Done.")
            coldcaller_logger.info(f"We spammed {caller_manager.spammed} people.")
        except Exception:
            raise


if __name__ == "__main__":
    main()
