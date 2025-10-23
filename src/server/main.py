import json, threading, time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware

import eeg.stream_thread

from .router import websocket_router
from .websocket import manager
from eeg.status import status_manager

from typing import Dict, Generator

lock = threading.Lock()

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get('/')
async def base() -> Dict:
    return {'message': 'Use the Force, Luke.'}

# Status Updater
@app.get('/status-updates')
async def status_update() -> StreamingResponse:

    def status_generator() -> Generator[str, None, None]:
        
        last_value: str = 'not connected'
        
        yield f"data: {json.dumps({'status': last_value})}\n\n"
        
        while True:
            
            with lock:
                if last_value != status_manager.status:
                    last_value = status_manager.status
                    # Format for SSE
                    yield f"data: {json.dumps({'status': last_value})}\n\n"
                
            time.sleep(0.1)

    return StreamingResponse(status_generator(), media_type="text/event-stream")

# Kb Updater
@app.get('/keybinding-que')
async def kb_update() -> StreamingResponse:

    def status_generator() -> Generator[str, None, None]:
        
        last_value: list = []
        
        yield f"data: {json.dumps({'que': last_value})}\n\n"
        
        while True:
            
            with lock:
                current_value = eeg.stream_thread.keybinding_que.copy()
                
            if last_value != current_value:
                last_value = current_value
                print('Updating Frontend')
                # Format for SSE
                yield f"data: {json.dumps({'que': last_value})}\n\n"
                
            time.sleep(0.1)

    return StreamingResponse(status_generator(), media_type="text/event-stream")

@app.websocket("/event-manager")
async def endpoint(websocket: WebSocket) -> None:

    await manager.connect(websocket)

    # Send initial ping to test
    await manager.ping()

    try:
        while True:
            # Receive messages from client (optional)
            data = await websocket.receive_text()
            message = json.loads(data)
            print(f"Received from client: {message}")

            await websocket_router(message, manager)

    except WebSocketDisconnect:
        manager.disconnect(websocket)
    except Exception as e:
        print(f"Error: {e}")
        manager.disconnect(websocket)