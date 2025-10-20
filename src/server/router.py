"""
Take websocket pings from front end and route them
to the correct function
"""
from .websocket import WebsocketManager, manager
from eeg.emulator import emulate_event_emission

from typing import Dict

async def websocket_router(message: Dict, manager: WebsocketManager) -> None:
    
    match message['type']:

        case 'ping':

            print('Recieved ping')

        case 'start_anomoly_detection':

            dp = emulate_event_emission()

            manager.send_gathered_example({
                s: d for s, d in zip(dp.sensors, dp.anom.data)
            })

        case _:

            print('Unknown message from frontend', message)