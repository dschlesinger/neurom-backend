import json

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .router import websocket_router
from .websocket import manager

from typing import Dict

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