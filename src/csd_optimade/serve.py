import tempfile
from pathlib import Path

from optimade_maker.serve import OptimakeServer


def cli():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("jsonl_path", type=str, default="optimade.jsonl")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    jsonl_path = Path(args.jsonl_path)
    if jsonl_path.is_file() and jsonl_path.name != "optimade.jsonl":
        # optimade-maker expects the file to be named `optimade.jsonl`
        tmp_path = Path(tempfile.mkdtemp())
        (tmp_path / "optimade.jsonl").symlink_to(jsonl_path.absolute())
        jsonl_path = tmp_path
    else:
        jsonl_path = jsonl_path.parent

    optimake_server = OptimakeServer(jsonl_path, args.port)
    optimake_server.start_api()
