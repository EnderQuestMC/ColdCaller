# ColdCaller

ColdCaller is a program that orchestrates cold calling Discord users with spam messages.

## Configuration

### Environment variables

* `COLDCALLER_MAX_USERS`: The maximum amount of users to create. Defaults to `-1`, which is no limit.
* `COLDCALLER_SERVER_INVITES`: A comma seperated list of invites to use to join servers. Example: `Oneshot,hypixel`

### Files in `config/`

* `message.md`: The message to send to a user after obtaining the ability to message them. Note that this is not full
  markdown because of missing features on discord. Required.
* `tokens.json`: A JSON array of emails and passwords. Optional. Fresh accounts will be added to this.
* `files`: Any files in the files folder will be attached to the message the bot sends.

If you are running in a non-interactive, like docker, or if you don't want to pass a captcha, you must define a token
in `tokens.json` instead of just defining an email and password.
