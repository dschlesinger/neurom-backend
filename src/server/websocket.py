import json

from fastapi import WebSocket, WebSocketDisconnect

from eeg.schema import DataPoint

from typing import Dict, List

class WebsocketManager:

    def __init__(self) -> None:
        self.current_connection: WebSocket | None = None

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()

        if self.current_connection is not None:
            print('Kicking old client off for new client')

        self.current_connection = websocket

        await self.ping()

    def disconnect(self, websocket: WebSocket) -> None:
        self.current_connection = None
        print('Websocket disconnected')

    async def ping(self) -> None:

        if self.current_connection is None:
            print('Tried to return but no websocket active', 'ping')
            return

        await self.current_connection.send_json({
            'type': 'ping',
            'data': {},
        })

    async def return_test_result(self, tr: Dict, anom_data: Dict) -> None:

        if self.current_connection is None:
            print('Tried to return but no websocket active', 'ping')
            return

        await self.current_connection.send_json({
            'type': 'test_result',
            'data': {
                'result': tr
            },
        })

        await self.current_connection.send_json({
            'type': 'gathered_datapoint',
            'data': {
                'potentials': anom_data
            },
        })

    async def send_gathered_example(self, anom_data: Dict) -> None:

        if self.current_connection is None:
            print('Tried to return but no websocket active', 'ping')
            return

        await self.current_connection.send_json({
            'type': 'gathered_datapoint',
            'data': {
                'potentials': anom_data
            },
        })

    async def test_on_data(self, tr: List) -> None:

        if self.current_connection is None:
            print('Tried to return but no websocket active', 'ping')
            return

        await self.current_connection.send_json({
            'type': 'update_test_data',
            'data': {
                'on_data_results': tr
            },
        })

    async def send_all_datasets(self, datasets: List[str]) -> None:

        if self.current_connection is None:
            print('Tried to return but no websocket active', 'ping')
            return

        await self.current_connection.send_json({
            'type': 'update_datasets',
            'data': {
                'datasets': datasets
            },
        })

        print('sent this')

    async def send_all_artifacts(self, artifacts: List[str]) -> None:

        if self.current_connection is None:
            print('Tried to return but no websocket active', 'ping')
            return

        await self.current_connection.send_json({
            'type': 'update_artifacts',
            'data': {
                'artifacts': artifacts
            },
        })

manager = WebsocketManager()