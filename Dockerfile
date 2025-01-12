FROM ubuntu:noble-20241118.1 AS base-packages

# Various GUI libs needed for CSD installer and Python API
RUN apt update && \
    apt install -y \
    wget \
    libfontconfig1 \
    libdbus-1-3 \
    libxcb-glx0 \
    libx11-xcb1 \
    libxcb-icccm4 \
    libxcb-image0 \
    libxcb-keysyms1 \
    libxcb-randr0 \
    libxcb-render-util0 \
    libxcb-shape0 \
    libxcb-sync1 \
    libxcb-xfixes0 \
    libxcb-xinerama0 \
    libxcb-xkb1 \
    libxext6 \
    libxkbcommon-x11-0 \
    libglx-mesa0 \
    libglib2.0-0t64 \
    libglx0 \
    libgl1 \
    libopengl0 \
    libegl1 \
    libgssapi-krb5-2 \
    && \
    rm -rf /var/lib/apt/lists/*

FROM base-packages AS csd-data

# Mount and then source any .env secrets that are required to download and activate the CSD
RUN --mount=type=secret,id=env \
    set -a && . /run/secrets/env && set +a && \
    wget -O /opt/csd-installer.sh ${CSD_INSTALLER_URL} && chmod u+x /opt/csd-installer.sh && \
    /opt/csd-installer.sh --root /opt/ccdc -c --accept-licenses install uk.ac.cam.ccdc.data.csd

FROM base-packages AS python-setup

WORKDIR /opt/csd-optimade

# Install GPG for encrypting the output CSD data
RUN apt update && apt install -y gpg git && rm -rf /var/lib/apt/lists/*

# Install uv for Python package management
COPY --from=ghcr.io/astral-sh/uv:0.4 /uv /usr/local/bin/uv
ENV UV_LINK_MODE=copy \
    UV_COMPILE_BYTECODE=1 \
    UV_PYTHON_DOWNLOADS=manual \
    UV_PYTHON=python3.11 \
    UV_NO_SYNC=1


# Set up Python 3.11 environment
RUN --mount=type=cache,target=/root/.cache/uv \
    uv python install 3.11 && \
    uv venv

FROM python-setup AS csd-ingester

WORKDIR /opt/csd-optimade

# Install and cache CSD Python API and its dependencies
RUN --mount=type=cache,target=/root/.cache/uv \
    uv pip install csd-python-api --extra-index-url https://pip.ccdc.cam.ac.uk

# Copy the CSD data into the ingestion image
COPY --from=csd-data /opt/ccdc/ccdc-data /opt/ccdc/ccdc-data
ENV CSD_DATA_DIRECTORY=/opt/ccdc/ccdc-data/csd

# Copy relevant csd-optimade build files only
COPY LICENSE pyproject.toml uv.lock  /opt/csd-optimade/
COPY src /opt/csd-optimade/src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --extra ingest --no-dev --extra-index-url https://pip.ccdc.cam.ac.uk

# Can be set at build time to retrigger the step below
ARG REINGEST=false

# Mount secrets to manually activate the CSD only when needed during ingestion
RUN --mount=type=secret,id=env \
    set -a && . /run/secrets/env && set +a && \
    mkdir -p /root/.config/CCDC && \
    echo "[licensing_v1]\nlicence_key=${CSD_ACTIVATION_KEY}" > /root/.config/CCDC/ApplicationServices.ini && \
    mkdir -p data && \
    # For some reason, this folder must be present when reading sqlite, otherwise it assumes it cannot
    mkdir -p /opt/ccdc/ccdc-software && \
    uv run --no-sync csd-ingest && \
    rm -rf /root/.config/CCDC/ApplicationServices.ini && \
    gzip -9 /opt/csd-optimade/csd-optimade.jsonl && \
    gpg --batch --passphrase ${CSD_ACTIVATION_KEY} --symmetric /opt/csd-optimade/csd-optimade.jsonl.gz

FROM csd-ingester AS csd-ingester-test
LABEL org.opencontainers.image.source="https://github.com/datalab-industries/csd-optimade"
LABEL org.opencontainers.image.description="Test environment for the csd-optimade project"

WORKDIR /opt/csd-optimade
ENV CSD_DATA_DIRECTORY=/opt/ccdc/ccdc-data/csd

RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --extra ingest --extra dev --extra-index-url https://pip.ccdc.cam.ac.uk

COPY tests /opt/csd-optimade/tests

COPY <<-"EOF" /opt/csd-optimade/test-entrypoint.sh
#!/bin/bash
set -e

if [ -z "$CSD_ACTIVATION_KEY" ]; then
 echo "CSD_ACTIVATION_KEY not set" >&2
 exit 1
fi

echo -e "[licensing_v1]\nlicence_key=${CSD_ACTIVATION_KEY}" > /root/.config/CCDC/ApplicationServices.ini
# For some reason, this folder must be present when reading sqlite, otherwise it assumes it cannot
mkdir -p /opt/ccdc/ccdc-software

exec uv run --no-sync pytest
EOF

RUN chmod +x /opt/csd-optimade/test-entrypoint.sh
CMD ["/opt/csd-optimade/test-entrypoint.sh"]

FROM python-setup AS csd-optimade-server
LABEL org.opencontainers.image.source="https://github.com/datalab-industries/csd-optimade"
LABEL org.opencontainers.image.description="Production environment for the csd-optimade project"

WORKDIR /opt/csd-optimade

# Copy the ingested CSD into the final image;
# could also ingest into database before this to avoid this step
COPY --from=csd-ingester /opt/csd-optimade/csd-optimade.jsonl.gz.gpg /opt/csd-optimade/csd-optimade.jsonl.gz.gpg

# Copy relevant csd-optimade build files only, this time do not install any extras
COPY LICENSE pyproject.toml uv.lock  /opt/csd-optimade/
COPY src /opt/csd-optimade/src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-dev

# Decrypt, decompress and serve the CSD data: requires the CSD_ACTIVATION_KEY at runtime
COPY <<-"EOF" /entrypoint.sh
#!/bin/bash
set -e

if [ -z "$CSD_ACTIVATION_KEY" ]; then
 echo "CSD_ACTIVATION_KEY not set" >&2
 exit 1
fi

gpg --batch --passphrase ${CSD_ACTIVATION_KEY} --decrypt /opt/csd-optimade/csd-optimade.jsonl.gz.gpg | gunzip > /opt/csd-optimade/csd-optimade.jsonl

exec uv run --no-sync csd-serve /opt/csd-optimade/csd-optimade.jsonl
EOF

RUN chmod +x /entrypoint.sh
CMD ["/entrypoint.sh"]
