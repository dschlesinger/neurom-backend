import threading, numpy as np, matplotlib.pyplot as plt, asyncio

from muselsl import stream, list_muses, view
from pylsl import StreamInlet, resolve_byprop
from time import sleep

import eeg.status
from cli.config import Settings
from eeg.detect import detect_anamolies
from .schema import DataPoint, Anomaly
from .utils import get_channel_names
from keybinding.handler import emit_keybind

from typing import Union, List

buffer = None
timestamp_buffer = None

events = []
sensors = None

# Lock for threading safely
lock = threading.Lock()

class MuseNotConnected(Exception):
    pass

# For now
keybindings_on: bool = True

def connect_to_eeg() -> Union['inlet', None]:
    """Returns inlet else none"""
    global sensors

    # Create and set event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:

        print('Finding muses...')
        muses = list_muses()

        print(muses)

        print('muses found', muses)

        # Handles len == 0 or None
        if not muses:
            print('No muses found')
            return None
        
        def stream_handler(address: str):

            import asyncio
            asyncio.set_event_loop(asyncio.new_event_loop())
            stream(address=address)
            
        muse_thread = threading.Thread(target=stream_handler, args=(muses[0]['address'],), daemon=True)
        muse_thread.start()

        muse_view = threading.Thread(target=view, daemon=True)
        muse_view.start()

        with lock: eeg.status.status_manager.set_status(stream_started=True)

        sleep(10)

        streams = resolve_byprop('type', 'EEG', timeout=5)
        try:
            inlet = StreamInlet(streams[0], max_chunklen=12)  # IndexError if streams is empty
        except IndexError:
            with lock: eeg.status.status_manager.set_status(stream_started=False)
            raise Exception('Could not find stream')
        
        sensors = get_channel_names(inlet)

        return inlet
    
    except Exception as e:
        with lock: eeg.status.status_manager.set_status(stream_started=False)
        return None
    
def eeg_loop(num_samples_to_buffer: int = Settings.BUFFER_LENGTH, current_mode: bool = False) -> None:
    global buffer, timestamp_buffer, events, sensors

    total_number_off_sample: int = 0

    last_event: Anomaly | None = None

    # Connect to eeg
    print('Connecting to EEG')
    inlet = connect_to_eeg()
    
    print(sensors)
    
    if sensors is not None:
    
        buffer = np.zeros((Settings.BUFFER_LENGTH, len(sensors)))
        timestamp_buffer = np.zeros((Settings.BUFFER_LENGTH,))
        
    else:
        # Force reconnection
        inlet = None
        # raise Exception('Could not find sensors')

    number_bad_sample = 0

    while True:

        try:

            if inlet is None:
                raise MuseNotConnected()
                
            samples, timestamps = inlet.pull_chunk(timeout=5, max_samples=Settings.MAX_SAMPLES_PER_CHUNK)

            samples = np.array(samples)

            timestamps = np.array(timestamps)

            num_samples = samples.shape[0]

            total_number_off_sample += num_samples

            if num_samples == 0:
                continue
            #     number_bad_sample += 1

            #     if number_bad_sample > 100:

            #         raise MuseNotConnected()

            #     continue

            # else:
            #     number_bad_sample = 0
            
            buffer = np.concat([buffer[num_samples:], samples])
            timestamp_buffer = np.concat([timestamp_buffer[num_samples:], timestamps])

            # Give time to buffer
            if total_number_off_sample > num_samples_to_buffer:

                if not eeg.status.status_manager.muse_has_buffered: print('Muse has buffered')

                with lock: eeg.status.status_manager.set_status(muse_has_buffered=True)
            
                with lock:

                    # print('Simulate detecting anomolies')

                    detect_anamolies(buffer, timestamp_buffer, events, sensors)

                if keybindings_on:

                    with lock:

                        if not events:
                            continue

                        elif last_event is None and events[-1].final:

                            last_event = events[-1]

                            emit_keybind(events)

                        elif last_event is not None and last_event.start != events[-1].start and events[-1].final:

                            emit_keybind(events)

                            last_event = events[-1]
                    
                    # # To avoid circular import, should redo this at somepoint very wack
                    # from detector.model import check_for_emission, model, Model
                    
                    # model = Model()
                    
                    # model.load_data('data_store/examples.json')
                    
                    # check_for_emission(model)

            # Sleep? No makes lag
            # sleep(0.01)

        except KeyboardInterrupt:
            pass
        except MuseNotConnected:

            print('Muse disconnected attempting reconnect')
            with lock: eeg.status.status_manager.set_status(stream_started=False)

            sleep(3)
            inlet = connect_to_eeg()
            
            print(sensors)
    
            if sensors is not None:
            
                buffer = np.zeros((Settings.BUFFER_LENGTH, len(sensors)))
                timestamp_buffer = np.zeros((Settings.BUFFER_LENGTH,))
                
            else:
                # Force reconnection
                inlet = None
                # raise Exception('Could not find sensors')
            
            continue

async def wait_for_new_event(classification: str) -> DataPoint:

    print('Gathering sample')

    prev_event_st: int = None
    found_datapoint: DataPoint | None = None

    with lock:

        if events:

            prev_event_st = events[-1].start
        
        else:

            prev_event_st = 0
            
    while True:

        with lock:

            for e in events[::-1]:

                if e.start == prev_event_st:
                    # We found our refrence
                    break

                if e.start != prev_event_st and e.final:

                    # we have a new event
                    print('Found sample')

                    found_datapoint = DataPoint(
                        classification=classification,
                        anom=e.copy()
                    )

                    return found_datapoint

        sleep(0.1)