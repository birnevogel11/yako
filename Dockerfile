FROM ubuntu:24.04

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY --from=ghcr.io/astral-sh/uv:latest /uvx /usr/local/bin/uvx

RUN set -ex \
    && apt update \
    && apt upgrade -y \
    && apt install -y build-essential curl wget git pigz moreutils

USER ubuntu

RUN set -ex \
    && uv python install 3.12 3.14 \
    && uv venv -p 3.14 /home/ubuntu/app \
    && uv pip install --python /home/ubuntu/app/bin/python3 tox ruff tox-uv ansible \
        ansible-lint pudb typer GitPython pyyaml cerberus \
    && mkdir -p /home/ubuntu/workspace

COPY --chown=ubuntu:ubuntu . /home/ubuntu/yako

RUN uv pip install --python /home/ubuntu/app/bin/python3 -e /home/ubuntu/yako

WORKDIR /home/ubuntu/workspace
