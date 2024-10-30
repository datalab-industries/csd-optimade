import tempfile
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
    )
    optimake_server.start_api()
