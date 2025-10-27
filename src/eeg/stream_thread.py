import threading, numpy as np, matplotlib.pyplot as plt, asyncio

from muselsl import stream, list_muses, view
from pylsl import StreamInlet, resolve_byprop
from time import sleep

import eeg.status
import keybinding.model
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

keybinding_que: List[str] = []

muse_thread: threading.Thread | None = None

class MuseNotConnected(Exception):
    pass

def connect_to_eeg() -> Union['inlet', None]:
    """Returns inlet else none"""
    global sensors, muse_thread

    # Create and set event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # Clean up old thread if it exists
        if muse_thread is not None and muse_thread.is_alive():
            print('Waiting for old muse thread to terminate...')
            muse_thread.join(timeout=5)  # Wait up to 5 seconds

        print('Finding muses...')
        muses = list_muses()

        print(muses)
        print('muses found', muses)

        if not muses:
            print('No muses found')
            return None
        
        def stream_handler(address: str):
            import asyncio
            asyncio.set_event_loop(asyncio.new_event_loop())
            stream(address=address)
            
        muse_thread = threading.Thread(target=stream_handler, args=(muses[0]['address'],), daemon=True)
        muse_thread.start()

        with lock: eeg.status.status_manager.set_status(stream_started=True)

        # Give the stream more time to initialize
        print('Waiting for stream to initialize...')
        sleep(2)  # Increased wait time

        streams = resolve_byprop('type', 'EEG', timeout=2)  # Increased timeout

        if not streams:
            print('No EEG streams found')
            with lock: eeg.status.status_manager.set_status(stream_started=False)
            return None

        # Viewing is erroring?
        # muse_view = threading.Thread(target=view, daemon=True)
        # muse_view.start()

        inlet = StreamInlet(streams[0], max_chunklen=12)
        
        sensors = get_channel_names(inlet)

        return inlet
    
    except Exception as e:
        print(f'Connection error: {e}')
        with lock: eeg.status.status_manager.set_status(stream_started=False)
        return None
    
def eeg_loop(num_samples_to_buffer: int = Settings.BUFFER_LENGTH, current_mode: bool = False) -> None:
    global buffer, timestamp_buffer, events, sensors, keybinding_que, muse_thread

    total_number_off_sample: int = 0

    prev_event_st: float = 0

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

    i = 0

    while True:

        try:

            if inlet is None or not muse_thread.is_alive():
                raise MuseNotConnected()
                
            samples, timestamps = inlet.pull_chunk(timeout=2, max_samples=Settings.MAX_SAMPLES_PER_CHUNK)

            samples = np.array(samples)

            timestamps = np.array(timestamps)

            # if i % 1000 == 0: print('Sample Shape', samples.shape)

            num_samples = samples.shape[0]

            # Detect not connect after buffering
            if (num_samples == 0 or samples.shape[0] == 0) and eeg.status.status_manager.muse_has_buffered:
                number_bad_sample += 1

                if number_bad_sample > 100:

                    number_bad_sample = 0
                    raise MuseNotConnected()

                continue

            else:

                number_bad_sample = 0

            if num_samples != 0:
                total_number_off_sample += num_samples

            try:
            
                buffer = np.concat([buffer[num_samples:], samples])
                timestamp_buffer = np.concat([timestamp_buffer[num_samples:], timestamps])

            except ValueError:

                print(f'Skipping iteration found sample with shape {samples.shape}')
                continue

            i += 1

            # Give time to buffer
            if total_number_off_sample > num_samples_to_buffer:

                if not eeg.status.status_manager.muse_has_buffered: print('Muse has buffered')

                with lock: eeg.status.status_manager.set_status(muse_has_buffered=True)
            
                with lock:

                    # print('Simulate detecting anomolies')

                    detect_anamolies(buffer, timestamp_buffer, events, sensors)

                if eeg.status.keybinding_on:

                    with lock:

                        for e in events[::-1]:

                            if e.start == prev_event_st:
                                # We found our refrence
                                break

                            if e.start != prev_event_st and e.final:

                                # we have a new event
                                print('Found event', {e.data.shape})

                                c = keybinding.model.model.predict(e)

                                keybinding_que.append(c)

                                print(c)

                                delete = emit_keybind(keybinding_que)

                                if delete: 
                                    events = []
                                    keybinding_que = []

                                prev_event_st = e.start
                                break

        except KeyboardInterrupt:
            pass
        except MuseNotConnected:
            print('Muse disconnected attempting reconnect')
            with lock: 
                eeg.status.status_manager.set_status(stream_started=False)
                eeg.status.status_manager.set_status(muse_has_buffered=False)  # Reset buffer status

            # Reset counters
            total_number_off_sample = 0
            number_bad_sample = 0

            sleep(3)
            inlet = connect_to_eeg()
            
            print(f'Reconnection result: {inlet}')
            print(f'Sensors: {sensors}')

            # Reconnects but streams blank data?

            if sensors is not None and inlet is not None:
                buffer = np.zeros((Settings.BUFFER_LENGTH, len(sensors)))
                timestamp_buffer = np.zeros((Settings.BUFFER_LENGTH,))
            else:
                inlet = None
                print('Failed to reconnect, will retry...')
            
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