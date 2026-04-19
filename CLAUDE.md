# Claude Project Notes

## Overview
- neurom-backend is a Python backend for Muse EEG artifact detection and keybind emission.
- It exposes a FastAPI server with WebSocket and SSE endpoints for a frontend client.

## Key Paths
- src/cli/run.py: CLI entry point. Starts EEG loop thread and Uvicorn server.
- src/eeg/: EEG streaming, detection, schemas, and status.
- src/keybinding/: Keybind model and handler for emitting key and mouse actions.
- src/server/: FastAPI app, router, and websocket manager.
- data_store/: JSON datasets for artifact detection.
- keybind_store/: Stored keybinding configs.

## Setup
- Python >= 3.12
- Install dependencies:
  - pip install -r requirements.txt
- The project defines a console script:
  - neurom-run -> cli.run:main

## Run
- Start the server (starts EEG loop + FastAPI):
  - neurom-run
- Directly with Python:
  - python -m src.cli.run

## Notes
- The EEG stream requires a Muse device and muselsl.
- For key/mouse emission, pyautogui or PyDirectInput is used.
- WebSocket endpoint: /event-manager
- SSE endpoint: /keybinding-que

## Tests
- No formal test runner configured in this repo.
