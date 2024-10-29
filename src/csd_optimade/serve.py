from pathlib import Path

from optimade_maker.serve import OptimakeServer


def cli():
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("jsonl_path", type=str, default="optimade.jsonl")
    parser.add_argument("--port", type=int, default=5000)
    args = parser.parse_args()

    optimake_server = OptimakeServer(Path(args.jsonl_path), args.port)
    optimake_server.start_api()
