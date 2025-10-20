import argparse, uvicorn

from server.main import app

def main() -> None:
    parser = argparse.ArgumentParser(description='Main Muse and Frontend Connection Loop')    

    parser.add_argument('-d', '--dummy', action='store_true', help='Whether to run with out muse for debugging connection')

    args = parser.parse_args()

    print('Hello World from Run!')

    if args.dummy:
        print('Running in test mode')
        # TODO

    uvicorn.run(app, host="0.0.0.0", port=8000)

    