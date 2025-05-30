FROM ubuntu:noble-20241118.1 AS base-packages

# Various GUI libs needed for CSD installer and Python API
RUN apt update && \
    apt install -y \
    git \
    gpg \
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

ARG CSD_INSTALLER_URL=

RUN \
    # Mount and then source any .env secrets that are required to download and activate the CSD
    --mount=type=secret,id=csd-installer-url,env=CSD_INSTALLER_URL \
    # Download/use the installer and download CSD
    wget -O /opt/csd-installer.sh ${CSD_INSTALLER_URL} && chmod u+x /opt/csd-installer.sh; \
    /opt/csd-installer.sh --root /opt/ccdc -c --accept-licenses install uk.ac.cam.ccdc.data.csd

FROM base-packages AS python-setup

WORKDIR /opt/csd-optimade

# Install uv for Python package management
COPY --from=ghcr.io/astral-sh/uv:0.6.3 /uv /usr/local/bin/uv
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

# Only changes to the ingest module will trigger a rebuild; rest will be mounted
COPY ./src/csd_optimade/ingest.py /opt/csd-optimade/src/csd_optimade/ingest.py

# Copy relevant csd-optimade build files only
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=src,target=/opt/csd-optimade/src,rw=true \
    --mount=type=bind,source=LICENSE,target=/opt/csd-optimade/LICENSE \
    --mount=type=bind,source=README.md,target=/opt/csd-optimade/README.md \
    --mount=type=bind,source=pyproject.toml,target=/opt/csd-optimade/pyproject.toml \
    --mount=type=bind,source=uv.lock,target=/opt/csd-optimade/uv.lock \
    uv sync --locked --extra ingest --no-dev --extra-index-url https://pip.ccdc.cam.ac.uk && \
    # Remove unecessary mandatory deps from csd-python-api
    uv pip uninstall tensorflow tensorflow-estimator xgboost keras jax google-pasta opt-einsum nvidia-nccl-cu12

# Can be set at build time to retrigger the step below
ARG REINGEST=false
ARG CSD_NUM_STRUCTURES=

# Mount secrets to manually activate the CSD only when needed during ingestion
# and give builder a chunk /tmp to write to (both as a data directory, and as its own /tmp)
RUN --mount=type=secret,id=csd-activation-key,env=CSD_ACTIVATION_KEY \
    --mount=type=bind,source=src,target=/opt/csd-optimade/src,rw=true \
    --mount=type=bind,source=LICENSE,target=/opt/csd-optimade/LICENSE \
    --mount=type=bind,source=README.md,target=/opt/csd-optimade/README.md \
    --mount=type=bind,source=pyproject.toml,target=/opt/csd-optimade/pyproject.toml \
    --mount=type=bind,source=uv.lock,target=/opt/csd-optimade/uv.lock \
    --mount=type=bind,source=/tmp,target=/opt/csd-optimade/data,rw=true \
    --mount=type=bind,source=/tmp,target=/tmp,rw=true \
    mkdir -p /root/.config/CCDC && \
    echo "[licensing_v1]\nlicence_key=${CSD_ACTIVATION_KEY}" > /root/.config/CCDC/ApplicationServices.ini && \
    mkdir -p data && \
    # For some reason, this folder must be present when reading sqlite, otherwise it assumes it cannot
    mkdir -p /opt/ccdc/ccdc-software && \
    # Actually run the ingestion with the given args
    uv run --no-sync \
      csd-ingest \
      --num-structures ${CSD_NUM_STRUCTURES} && \
    rm -rf /root/.config/CCDC/ApplicationServices.ini && \
    gzip -9 /opt/csd-optimade/data/csd-optimade.jsonl && \
    gpg --batch --passphrase ${CSD_ACTIVATION_KEY} --symmetric /opt/csd-optimade/data/csd-optimade.jsonl.gz && \
    cp /opt/csd-optimade/data/csd-optimade.jsonl.gz.gpg /opt/csd-optimade/csd-optimade.jsonl.gz.gpg


FROM base-packages AS compress-csd-data

COPY --from=csd-data /opt/ccdc/ccdc-data/csd /tmp/csd
RUN --mount=type=secret,id=csd-activation-key,env=CSD_ACTIVATION_KEY \
    tar -czf /opt/csd.tar.gz -C /tmp csd && \
    rm -rf /tmp/csd && \
    gpg --batch --passphrase ${CSD_ACTIVATION_KEY} --symmetric /opt/csd.tar.gz

FROM python-setup AS csd-ingester-test
LABEL org.opencontainers.image.source="https://github.com/datalab-industries/csd-optimade"
LABEL org.opencontainers.image.description="Test environment for the csd-optimade project"

# Copy the CSD data into the test image
WORKDIR /opt/ccdc/ccdc-data
COPY --from=compress-csd-data /opt/csd.tar.gz.gpg /opt/csd.tar.gz.gpg

WORKDIR /opt/csd-optimade
ENV CSD_DATA_DIRECTORY=/opt/ccdc/ccdc-data/csd

# Copy relevant csd-optimade build files only
COPY LICENSE pyproject.toml uv.lock  /opt/csd-optimade/
COPY src /opt/csd-optimade/src
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --extra ingest --extra dev --extra-index-url https://pip.ccdc.cam.ac.uk && \
    # Remove unecessary mandatory deps from csd-python-api
    uv pip uninstall tensorflow tensorflow-estimator xgboost keras jax google-pasta opt-einsum nvidia-nccl-cu12 && \
    # Remove duplicated csd-python-api install
    rm -rf /opt/csd-optimade/.venv/lib/python3.11/site-packages/lib/ccdc

COPY tests /opt/csd-optimade/tests

COPY <<-"EOF" /opt/csd-optimade/test-entrypoint.sh
#!/bin/bash
set -e

if [ -z "$CSD_ACTIVATION_KEY" ]; then
 echo "CSD_ACTIVATION_KEY not set" >&2
 exit 1
fi

mkdir -p /root/.config/CCDC
echo -e "[licensing_v1]\nlicence_key=${CSD_ACTIVATION_KEY}" > /root/.config/CCDC/ApplicationServices.ini
# For some reason, this folder must be present when reading sqlite, otherwise it assumes it cannot
mkdir -p /opt/ccdc/ccdc-software

echo "Decrypting CSD data..."
time gpg --batch --passphrase ${CSD_ACTIVATION_KEY} --decrypt /opt/csd.tar.gz.gpg > /opt/csd.tar.gz
time tar -xzf /opt/csd.tar.gz -C /opt/ccdc/ccdc-data
echo "Decompressing CSD data..."

echo "Running tests..."
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
    uv sync --locked --no-dev && \
    # Remove unecessary mandatory deps from csd-python-api
    uv pip uninstall tensorflow tensorflow-estimator xgboost keras jax google-pasta opt-einsum nvidia-nccl-cu12

# Decrypt, decompress and serve the CSD data: requires the CSD_ACTIVATION_KEY at runtime
COPY <<-"EOF" /entrypoint.sh
#!/bin/bash
set -e

if [ -z "$CSD_ACTIVATION_KEY" ]; then
 echo "CSD_ACTIVATION_KEY not set" >&2
 exit 1
fi

if [ "$CSD_OPTIMADE_INSERT" = "1" ] || [ "$CSD_OPTIMADE_INSERT" = "true" ]; then
    # Run the API twice: once to wipe and reinsert the data then exit, the second to run the API
    (gpg --batch --passphrase ${CSD_ACTIVATION_KEY} --decrypt /opt/csd-optimade/csd-optimade.jsonl.gz.gpg | gunzip > /opt/csd-optimade/csd-optimade.jsonl;
    exec uv run --no-sync csd-serve --port 5001 --exit-after-insert --drop-first /opt/csd-optimade/csd-optimade.jsonl) &
fi

# Run CLI with 'fake' file
touch /tmp/csd-optimade.jsonl
exec uv run --no-sync csd-serve --no-insert /tmp/csd-optimade.jsonl

EOF

RUN chmod +x /entrypoint.sh
CMD ["/entrypoint.sh"]
