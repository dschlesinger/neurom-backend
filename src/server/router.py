"""
Take websocket pings from front end and route them
to the correct function
"""
import json

import eeg.data, eeg.status, eeg.stream_thread
import keybinding.model, keybinding.handler

from .websocket import WebsocketManager, manager
# from eeg.emulator import emulate_event_emission
from eeg.stream_thread import wait_for_new_event

from typing import Dict

async def websocket_router(message: Dict, manager: WebsocketManager) -> None:
    
    match message['type']:

        case 'ping':

            print('Recieved ping')

        case 'start_test':

            dp = await wait_for_new_event(message['data']['classification'])

            pred = keybinding.model.model.predict(dp.anom)

            await manager.return_test_result({
                'guess': pred,
                'correct': message['data']['classification']
            }, [
                {
                    'sensor': s,
                    'data': d
                }   for s, d in zip(dp.anom.sensors, dp.anom.data.T.tolist())
            ])

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

        case 'turn_keybinds':

            print(f'Turning Keybinds {message['data']['state']}')

            eeg.status.keybinding_on = message['data']['state']

        case 'set_keybinds':

            print(f'Setting keybindings')

            keybinding.handler.keybindings = message['data']['keybindings']

        case 'save_keybinds':

            print('Saving keybinds')

            with open(f'keybind_store/{message["data"]["name"]}.json', 'w') as j:

                j.write(json.dumps(message['data']['keybinds']))

            await manager.send_all_keybindings()

        case 'get_functional_kbs':

            await manager.send_function_kbs()

        case 'load_keybinds':

            print('Loading keybinds')

            with open(f'keybind_store/{message["data"]["name"]}.json', 'r') as j:

                keybinding.handler.keybindings = json.load(j)

            await manager.update_keybindings()

        case 'get_all_keybindings':

            await manager.send_all_keybindings()
        
        case 'clear_que':

            eeg.stream_thread.keybinding_que = []
        
        case 'debug_datapoint':

            print(eeg.data.datapoints.__len__())

        case 'test_on_data':

            await manager.test_on_data(keybinding.model.model.test_on_data())

        case 'last_anomoly_no_good':

            # Remove last
            if eeg.data.datapoints:
                eeg.data.datapoints.pop()

        case 'change_used_datasets':

            keybinding.model.model.load_data([
                f'data_store/{ds}.json' for ds in message['data']['used_datasets']
            ])

            await manager.send_all_artifacts(keybinding.model.model.get_all_classifications())
            
        case 'list_available_datasets':
            await manager.send_all_datasets([ds.removesuffix('.json') for ds in keybinding.model.model.get_all_datasets()])

        case 'save_dataset':

            name = message['data']['dataset_name']

            with open(f'data_store/{name}.json', 'w') as j:

                j.write(
                    json.dumps(
                        [d.model_dump() for d in eeg.data.datapoints]
                    )
                )

            eeg.data.datapoints = []

            await manager.send_all_datasets([ds.removesuffix('.json') for ds in keybinding.model.model.get_all_datasets()])

        case _:

            print('Unknown message from frontend', message)