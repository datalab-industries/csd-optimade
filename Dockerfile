FROM ubuntu:24.04 AS base-packages

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
RUN apt update && apt install -y gpg && rm -rf /var/lib/apt/lists/*

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
ENV CSD_DATA_DIRECTORY=/opt/ccdc/ccdc-data

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
    uv run --no-sync csd-ingest && \
    rm -rf /root/.config/CCDC/ApplicationServices.ini && \
    gzip -9 /opt/csd-optimade/csd-optimade.jsonl && \
    gpg --batch --passphrase ${CSD_ACTIVATION_KEY} --symmetric /opt/csd-optimade/csd-optimade.jsonl.gz

FROM python-setup AS csd-server

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
# CMD ["uv", "run", "--no-sync", "csd-serve", "/opt/csd-optimade/csd-optimade.jsonl.gz.gpg"]
