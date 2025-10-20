import argparse, uvicorn, threading

from server.main import app
from eeg.stream_thread import eeg_loop

def main() -> None:
    parser = argparse.ArgumentParser(description='Main Muse and Frontend Connection Loop')    

    parser.add_argument('-d', '--dummy', action='store_true', help='Whether to run with out muse for debugging connection')

    args = parser.parse_args()

    print('Hello World from Run!')

    if args.dummy:
        print('Running in test mode')
        # TODO

    muse_loop_thread = threading.Thread(target=eeg_loop, daemon=True)
    muse_loop_thread.start()

    uvicorn.run(app, host="0.0.0.0", port=8000)

    