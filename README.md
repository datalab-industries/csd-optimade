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

## Rough timings

For the first 1000 CSD entries (AMD Ryzen 7 PRO 7840U):

|Backend|# processes|`OMP_NUM_THREADS`|chunk size|timing (s)
|:--:|:--:|--:|--:|--|
|ASE|8|`null`|100|3:31.95|
|ASE|4|`null`|100|3:38.65|
|ASE|1|`null`|100|4:33.13|
|ASE|8|1|100|3:05.81|
|ASE|4|1|100|3:13.64|
|ASE|1|1|100|3:34.16|

Dominated by a few slow structures that clog up the multiprocessing pool.
