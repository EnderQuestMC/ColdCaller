# ColdCaller

ColdCaller is a program that orchestrates cold calling Discord users with spam messages.

At the moment, it can only use predefined users. In the future, it will create users at runtime.

## Configuration

### Files in `config/`

* `message.md`: The message to send to a user after obtaining the ability to message them. Note that this is not full markdown because of missing features on discord. Required.
* `tokens.json`: A JSON array of tokens and passwords. Required.
