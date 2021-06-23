# ColdCaller

ColdCaller is a program that orchestrates cold calling Discord users with spam messages. 

At runtime, it will create some user tokens. 

## Configuration

### Files in `config/`

* `message.md`: The message to send to a user after obtaining the ability to message them. Note that this is not full markdown because of missing features on discord. Required.
* `tokens.json`: A JSON array of tokens and passwords. Required.
