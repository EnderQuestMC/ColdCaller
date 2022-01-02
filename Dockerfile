# syntax=docker/dockerfile:1

FROM python:3.9.6-slim-buster

RUN DEBIAN_FRONTEND=noninteractive apt-get update
RUN DEBIAN_FRONTEND=noninteractive apt-get upgrade -y
RUN DEBIAN_FRONTEND=noninteractive apt-get install -y git

WORKDIR /app

COPY . .

RUN "pip install ."

CMD [ "python -m coldcaller"]
