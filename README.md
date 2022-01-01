# ColdCaller

ColdCaller is a program that orchestrates cold calling Discord users with spam messages.

At the moment, it can only use predefined users. In the future, it will create users at runtime.

## Configuration

### Files in `config/`

* `message.md`: The message to send to a user after obtaining the ability to message them. Note that this is not full markdown because of missing features on discord. Required.
* `tokens.json`: A JSON array of emails and passwords. Required.

If you are running in a non-interactive, like docker, or if you don't want to pass a captcha, you must define a token in `tokens.json` instead of just defining an email and password.
