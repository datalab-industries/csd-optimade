# CSD OPTIMADE API

This repo contains some prototyping work on creating an OPTIMADE API for
searching and accessing structures from the Cambridge Structural Database (CSD)
via the CSD Python API.

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
Any attempts to use CSD data will additionally require a CSD license and [appropriate configuration](https://downloads.ccdc.cam.ac.uk/documentation/API/installation_notes.html#installation-options).

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
and combined into a single JSONLines on completion, with name
`<--run-name>-optimade.jsonl`.

### Creating an OPTIMADE API

The `csd-serve` entrypoint provides a thin wrapper around the
[`optimade-maker`](https://github.com/materialscloud-org/optimade-maker/) tool,
and bundles the simple configuration required to launch a local OPTIMADE API.
Just provide the path to your combined OPTIMADE JSONLines file:

```shell
csd-serve <path-to-optimade-jsonl>
```

You should now be able to try out some queries locally, either in the browser or
with a tool like `curl`:

```shell
curl http://localhost:5000/structures?filter=elements HAS "C"
```
