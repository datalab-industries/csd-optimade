import tempfile
import typing
from pathlib import Path

from optimade_maker.serve import OptimakeServer


def cli():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("jsonl_path", type=str, default="optimade.jsonl")
    parser.add_argument(
        "--port", type=int, default=5000, help="Port to run the OPTIMADE API on."
    )
    parser.add_argument(
        "--no-insert",
        action="store_true",
        help="Do not insert the JSONL file into the database.",
    )
    parser.add_argument(
        "--mongo-uri",
        type=str,
        help="An optional MongoDB URI to use, instead of the in-memory database.",
    )
    args = parser.parse_args()

    jsonl_path = Path(args.jsonl_path)
    if jsonl_path.is_file() and jsonl_path.name != "optimade.jsonl":
        # optimade-maker expects the file to be named `optimade.jsonl`
        tmp_path = Path(tempfile.mkdtemp())
        (tmp_path / "optimade.jsonl").symlink_to(jsonl_path.absolute())
        jsonl_path = tmp_path
    else:
        jsonl_path = jsonl_path.parent

    # kwargs to override optimade-maker defaults, if set
    override_kwargs: dict[str, typing.Any] = {}
    if args.no_insert:
        override_kwargs["insert_from_jsonl"] = None

    # Allow user to specify a real MongoDB
    mongo_uri = args.mongo_uri
    if mongo_uri:
        import logging

        import pymongo

        logging.getLogger("pymongo").setLevel(logging.WARNING)
        test_client = None
        try:
            test_client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=1000)
        except pymongo.ServerSelectionTimeoutError:
            pass
        if test_client and not test_client.server_info():
            raise ValueError(
                f"Could not connect to MongoDB using the provided URI: {mongo_uri}"
            )

    optimake_server = OptimakeServer(
        jsonl_path,
        args.port,
        mongo_uri=mongo_uri,
        database_backend="mongodb" if mongo_uri else "mongomock",
        provider_fields={
            "structures": [
                {
                    "name": "_csd_lattice_parameters",
                    "type": "float",
                    "description": "The ((a, b, c), (alpha, beta, gamma)) unit cell parameters.",
                },
                {
                    "name": "_csd_deposition_date",
                    "type": "timestamp",
                    "description": "The date the structure was deposited.",
                },
                {
                    "name": "_csd_ccdc_number",
                    "type": "integer",
                    "description": "The CCDC deposition ID.",
                },
                {
                    "name": "_csd_space_group_symbol_hermann_mauginn",
                    "type": "string",
                    "description": "The space group symbol for the crystal, following the Hermann-Mauguin notation.",
                },
                {
                    "name": "_csd_inchi",
                    "type": "string",
                    "description": "CSD InChI string.",
                },
                {
                    "name": "_csd_inchi_key",
                    "type": "string",
                    "description": "CSD InChIKey.",
                },
                {
                    "name": "_csd_smiles",
                    "type": "string",
                    "description": "CSD SMILES string.",
                },
                {
                    "name": "_csd_z_value",
                    "type": "integer",
                    "description": "The number of formula units in the unit cell.",
                },
                {
                    "name": "_csd_z_prime",
                    "type": "integer",
                    "description": "The number of formula units in the asymmetric unit.",
                },
            ]
        },
        provider={
            "prefix": "csd",
            "name": "Cambridge Structural Database",
            "description": "A database of crystal structures curated by the Cambridge Crystallographic Data Centre.",
        },
        **override_kwargs,
    )
    optimake_server.start_api()
