# CSD OPTIMADE API

This repo contains prototyping work for creating an [OPTIMADE
API](https://optimade.org) for searching and accessing structures
from the [Cambridge Structural Database (CSD)](https://www.ccdc.cam.ac.uk/structures).

The structures are accessed via the [CSD Python
API](https://downloads.ccdc.cam.ac.uk/documentation/API/) and cast to the
OPTIMADE format; the
[`optimade-maker`](https://github.com/materialscloud-org/optimade-maker/) and
[`optimade-python-tools`](https://github.com/Materials-Consortia/optimade-python-tools/)
are then used to launch a local OPTIMADE API.

## Installation

After cloning this repository and using some appropriate method of creating a virtual environment (current recommendation is [`uv`](https://github.com/astral-sh/uv)), this package can be installed with

```shell
uv sync
```

or

```shell
pip install . --extra-index-url https://pip.ccdc.cam.ac.uk
```

Note that the extra index URL is required to install the `csd-python-api` package.
Any attempts to use CSD data will additionally require a CSD license and
[appropriate configuration](https://downloads.ccdc.cam.ac.uk/documentation/API/installation_notes.html#installation-options).

## Usage

### Ingesting CSD data

The CSD can be ingested into the OPTIMADE format using the `csd-ingest` entrypoint:

```shell
csd-ingest
```

This will use multiple processes (controlled by `--num-processes`) to ingest the
local copy of the CSD database in chunks of size `--chunk-size` until the target
`--num-structures` has been reached (defaults to the entire CSD).
Each batch will be written to an [OPTIMADE JSONLines file](https://github.com/Materials-Consortia/OPTIMADE/pull/531),
and combined into a single JSONLines file (~ 5.5 GB for the entire CSD, or 2 GB compressed) on completion, with name
`<--run-name>-optimade.jsonl`.

Depending on parallelisation, this process should take a few minutes to ingest
the entire CSD on consumer hardware (around 10 minutes with 8 processes on an AMD Ryzen 7 PRO 7840U mobile
processor, requiring around 3 GB of RAM per process with the default chunk size of 100k).

### Creating an OPTIMADE API

The `csd-serve` entrypoint provides a thin wrapper around the
[`optimade-maker`](https://github.com/materialscloud-org/optimade-maker/) tool,
and bundles the simple configuration required to launch a local OPTIMADE API
with a simple in-memory database (if `--mongo-uri` is provided, a real MongoDB
backend will be used).
Just provide the path to your combined OPTIMADE JSONLines file:

```shell
csd-serve <path-to-optimade-jsonl>
```

You should now be able to try out some queries locally, either in the browser or
with a tool like `curl`:

```shell
curl http://localhost:5000/structures?filter=elements HAS "C"
```

## Funding

This project was developed by [datalab industries ltd.](https://datalab.industries), on behalf of the UK's [Physical Sciences Data Infrastructure (PSDI)](https://psdi.ac.uk), supported by the [Cambridge Crystallographic Data Centre (CCDC)](https://www.ccdc.cam.ac.uk/).
