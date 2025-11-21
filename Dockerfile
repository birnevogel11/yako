FROM ubuntu:24.04

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY --from=ghcr.io/astral-sh/uv:latest /uvx /usr/local/bin/uvx

RUN set -ex \
    && apt update \
    && apt upgrade -y \
    && apt install -y build-essential curl wget git pigz moreutils

COPY ./scripts/entrypoint.sh /entrypoint.sh
COPY . /home/ubuntu/roly

RUN set -ex \
    && chown -R "$(id -u ubuntu):$(id -g ubuntu)" /home/ubuntu/roly

USER ubuntu

RUN set -ex \
    && uv python install 3.14 \
    && uv venv -p 3.14 /home/ubuntu/app \
    && uv pip install --python /home/ubuntu/app/bin/python3 tox black ruff tox-uv ansible \
        ansible-lint pudb typer GitPython pyyaml cerberus

RUN set -ex \
    && uv pip install --python /home/ubuntu/app/bin/python3 -e /home/ubuntu/roly \
    && mkdir -p /home/ubuntu/workspace

WORKDIR /home/ubuntu/workspace
