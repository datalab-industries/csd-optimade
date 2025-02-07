import argparse
import tempfile
import typing
from pathlib import Path

from optimade_maker.serve import OptimakeServer

from csd_optimade.fields import generate_csd_provider_fields


def cli():
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
        "--exit-after-insert",
        action="store_true",
        help="Exit the API after inserting the JSONL file.",
    )
    parser.add_argument(
        "--drop-first",
        action="store_true",
        help="Drop the database before inserting the JSONL file.",
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

    if args.exit_after_insert:
        override_kwargs["exit_after_insert"] = True

    # Allow user to specify a real MongoDB
    mongo_uri = args.mongo_uri
    if mongo_uri:
        import logging

        import pymongo

        logging.getLogger("pymongo").setLevel(logging.WARNING)
        parsed_uri = pymongo.uri_parser.parse_uri(mongo_uri)
        database_name = parsed_uri.get("database")
        if not database_name:
            raise ValueError(
                f"Could not parse database name from MongoDB URI: {mongo_uri}"
            )
        test_client = None
        try:
            test_client = pymongo.MongoClient(mongo_uri, serverSelectionTimeoutMS=1000)
        except pymongo.ServerSelectionTimeoutError:
            pass
        if test_client and not test_client.server_info():
            raise ValueError(
                f"Could not connect to MongoDB using the provided URI: {mongo_uri}"
            )

        if args.drop_first and test_client:
            test_client.drop_database(database_name)

    override_kwargs["license"] = "https://www.ccdc.cam.ac.uk/licence-agreement"

    optimake_server = OptimakeServer(
        jsonl_path,
        args.port,
        mongo_uri=mongo_uri,
        database_backend="mongodb" if mongo_uri else "mongomock",
        provider_fields=generate_csd_provider_fields(),
        provider={
            "prefix": "csd",
            "name": "Cambridge Structural Database",
            "description": "A database of crystal structures curated by the Cambridge Crystallographic Data Centre.",
            "homepage=": "https://www.ccdc.cam.ac.uk",
        },
        **override_kwargs,
    )
    optimake_server.start_api()
