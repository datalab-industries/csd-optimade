# CSD OPTIMADE API

This repo contains some prototyping work on creating an OPTIMADE API for
searching and accessing structures from the Cambridge Structural Database (CSD)
via the CSD Python API.

## Installation

After cloning this repository and using some appropriate method of creating a virtual environment (current recommendation is [`uv`](https://github.com/astral-sh/uv)), this package can be installed with

```shell
pip install . --extra-index-url https://pip.ccdc.cam.ac.uk
```

Note that the extra index URL is required to install the `csd-python-api` package.
Any attempts to ingest CSD data will additionally require a CSD license and appropriate
configuration.
