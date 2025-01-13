<div align="center" style="padding: 2em;">
<span style="padding: 1em">
<img height="70px" align="center" src="https://matsci.org/uploads/default/original/2X/b/bd2f59b3bf14fb046b74538750699d7da4c19ac1.svg">
</span>
</div>

# <div align="center">CSD OPTIMADE API</div>

This repo contains prototyping work for creating an [OPTIMADE
API](https://optimade.org) for searching and accessing structures
from the [Cambridge Structural Database (CSD)](https://www.ccdc.cam.ac.uk/structures).

The structures are accessed via the [CSD Python
API](https://downloads.ccdc.cam.ac.uk/documentation/API/) and cast to the
OPTIMADE format; the
[`optimade-maker`](https://github.com/materialscloud-org/optimade-maker/) and
[`optimade-python-tools`](https://github.com/Materials-Consortia/optimade-python-tools/)
are then used to launch a local OPTIMADE API.

## Roadmap

Estimated date for completion: March 2025.

- [x] Set up ingestion pipeline for CSD database to allow querying via local OPTIMADE API.
- [ ] Collaborate on and collate cheminformatics property definitions as part of wider [OPTIMADE cheminformatics initiative](https://github.com/Materials-Consortia/namespace-cheminformatics/).
- [ ] Get feedback on pipeline for correctness/robustness, and incrementally deal with problematic cases.
- [ ] Deploy ingestion service behind PSDI authentication gateway as a data service that can be used by e.g., cross-search platform, that updates on each CSD data release.


## Installation

After cloning this repository and using some appropriate method of creating a virtual environment (current recommendation is [`uv`](https://github.com/astral-sh/uv)), this package can be installed with

```shell
git clone git@github.com:datalab-industries/csd-optimade
cd csd-optimade
uv sync --extra-index-url https://pip.ccdc.cam.ac.uk
```

or

```shell
git clone git@github.com:datalab-industries/csd-optimade
cd csd-optimade
pip install . --extra-index-url https://pip.ccdc.cam.ac.uk
```

Note that the extra index URL is required to install the `csd-python-api` package.

> [!IMPORTANT]  
>  Any attempts to use CSD data will additionally require a CSD license and [appropriate configuration](https://downloads.ccdc.cam.ac.uk/documentation/API/installation_notes.html#installation-options).


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

## Containerized version

For ease of deployment, as containerised version of the ingestion pipeline is available.

> [!IMPORTANT]
> You should verify that your license agreement allows for any kind of deployment outside of your private network; it likely does not.

To build the container from scratch, you need both a time-limited CSD installer
download link (`CSD_INSTALLER_URL`), and your activation key
(`CSD_ACTIVATION_KEY`).

> [!NOTE]
> As of January 2025, you can request your time-limited CSD installer link at https://www.ccdc.cam.ac.uk/support-and-resources/download-the-csd/. Once you receive the email, the `CSD_INSTALLER_URL` should be the one listed as "CSD Portfolio <version> Linux Online Installer (recommended, small download)".

These should be stored in a `.env` file that is available both at build time and runtime.
Note, managing these secrets requires a recent Docker version that includes
Buildx.

Once configured, you can build the container with

```shell
docker build --secret id=env,src=.env -t csd-optimade .
```

This will install the CSD inside the container, run the ingestion pipeline and
prepare an encrypted version of the CSD in the OPTIMADE JSONLines format.
The file can be decrypted with your `CSD_ACTIVATION_KEY`.

To launch the container (which will decrypt the file and start the OPTIMADE
API locally):

```shell
docker run --env-file .env -p 5000:5000 csd-optimade
```

For development, you may prefer to use the bake definitions in
`docker-bake.hcl` to build and tag the relevant build stages.

## Contributing and Getting Help

All development of this package (bug reports, suggestions, feedback and pull requests) occurs in the [csd-optimade GitHub repository](https://github.com/datalab-industries/csd-optimade).
Contribution guidelines and tips for getting help can be found in the [contributing notes](CONTRIBUTING.md).


## Funding

This project was developed by [datalab industries ltd.](https://datalab.industries), on behalf of the UK's [Physical Sciences Data Infrastructure (PSDI)](https://psdi.ac.uk), supported by the [Cambridge Crystallographic Data Centre (CCDC)](https://www.ccdc.cam.ac.uk/).


<div align="center">
<a href="https://psdi.ac.uk"><img src='https://github.com/user-attachments/assets/19d8a74d-f3d0-4825-8a71-4eba1b6392de' width=400/></a>
</div>
