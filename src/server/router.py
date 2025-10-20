"""
Take websocket pings from front end and route them
to the correct function
"""
from .websocket import WebsocketManager, manager
from eeg.emulator import emulate_event_emission
import eeg.data
from eeg.stream_thread import wait_for_new_event

from typing import Dict

async def websocket_router(message: Dict, manager: WebsocketManager) -> None:
    
    match message['type']:

        case 'ping':

            print('Recieved ping')

        case 'start_anomoly_detection':

            dp = await wait_for_new_event(message['data']['classification'])

            eeg.data.datapoints.append(dp)

            print(eeg.data.datapoints.__len__())

            await manager.send_gathered_example([
                {
                    'sensor': s,
                    'data': d
                }   for s, d in zip(dp.anom.sensors, dp.anom.data.T.tolist())
            ])

        case 'reset_anomoly_gathering':

            eeg.data.datapoints = []
        
        case 'debug_datapoint':

            print(eeg.data.datapoints.__len__())

        case 'last_anomoly_no_good':

            # Remove last
            eeg.data.datapoints.pop()

        case _:

            print('Unknown message from frontend', message)