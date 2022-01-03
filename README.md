# ColdCaller

ColdCaller is a program that orchestrates cold calling Discord users with spam messages.

It can create accounts, but these accounts must currently have a verified phone number.

## WARNING

This project is for evaluation purposes only. Please, PLEASE don't use this maliciously. This is just a fun winter break
project.

## Configuration

### Files in `config/`

* `message.md`: The message to send to a user after obtaining the ability to message them. Note that this is not full
  markdown because of missing features on discord. Required.
    * You may use the placeholder `spamee` for the person being spammed.
        * This is a `discord.User`, so you can use properties like `spamee.mention`
    * You may use the placeholder `spamer` for the bot sending the message.
        * This is a `discord.ClientUser`, so you can use properties like `spamer.mention`
* `tokens.json`: A JSON array of emails and passwords. Optional. Fresh accounts will be added to this.
* `embed.json`: A embed to send, in JSON form.
* `files`: Any files in the files folder will be attached to the message the bot sends.

If you are running in a non-interactive, like docker, or if you don't want to pass a captcha, you must define a token
in `tokens.json` instead of just defining an email and password.

### CLI

You can also use it entirely from the command line. Simply install using pip ```pip install git+https://github.com/regulad/ColdCaller.git```.

You will need `pip3`, Python 3.10, and `git`.

You can use the fancy new package manager in Windows: `winget`

```winget install -e --id Python.Python.3```

```winget install -e --id Git.Git```

```winget install -e --id GitHub.GitLFS```

I have also compiled a [bundle of scripts](https://gist.github.com/regulad/3ebad109d47a0546a09d0395c45fc228) for installing these tools quickly on a debian-based system.

You can see help with `coldcaller -h`.
