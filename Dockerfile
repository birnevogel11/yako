FROM ubuntu:24.04

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv
COPY --from=ghcr.io/astral-sh/uv:latest /uvx /usr/local/bin/uvx

RUN set -ex \
    && apt update \
    && apt upgrade -y \
    && apt install -y build-essential curl wget git pigz moreutils

COPY . /roly

RUN set -ex \
    && uv python install 3.13 \
    && uv venv -p 3.13 /app \
    && uv pip install --python /app/bin/python3 tox black ruff tox-uv ansible \
        ansible-lint pudb typer GitPython pyyaml cerberus

RUN set -ex \
    && uv pip install --python /app/bin/python3 -e /roly \
    && mkdir -p /workspace

WORKDIR /workspace

COPY ./scripts/entrypoint.sh /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
