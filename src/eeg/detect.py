import numpy as np, matplotlib.pyplot as plt

from itertools import repeat
from typing import List, Dict

from pydantic import BaseModel, ConfigDict, model_serializer

from cli.config import Settings

from .schema import Anomaly

def end_event(event: Anomaly, buffer: np.ndarray, timestamps: np.ndarray) -> None:

    offset: int = 25

    lower_bound = max(np.searchsorted(timestamps, event.start) - offset, 0)
    upper_bound = min(np.searchsorted(timestamps, event.end) + offset, buffer.shape[0])

    # Expand buffer
    event.data = buffer[lower_bound : upper_bound]

    # Update previous to be final
    event.final = True

def detect_anamolies(buffer: np.ndarray, timestamps: np.ndarray, events: List, sensors: List[str], lookback: int = 3) -> None:

    # kernel: np.ndarray = np.array([*[-1/delta_lookback for i in range(delta_lookback)], 1, *[0 for i in range(delta_lookback)]])

    # deltas: np.ndarray = np.apply_along_axis(lambda x: np.convolve(x, kernel, mode='same'), 
    #                           axis=0, arr=buffer)
    
    # Dont have to check for zeros as we wait to fill buffer for procceding
    m = buffer.mean(axis=0)
    s = buffer.std(axis=0)
    v = Settings.EVENT_STD

    ca = channel_allowances = np.array([50.0])

    mean_val = buffer[-lookback:].mean(axis=0)
    lower = np.minimum(m - v * s, m - ca)
    upper = np.maximum(m + v * s, m + ca)

    now = timestamps[-1].item()

    # Gathering is event based, if a single event then not another one will not
    # Check current event should be over
    if np.any((mean_val < lower) | (mean_val > upper)): 

        # No events
        if not events:
            events.append(
                Anomaly(
                    start=now,
                    end=now,
                    data=buffer[-1],
                    sensors=sensors,
                )
            )   
        # Check if previous event can be merged
        elif not events[-1].final and now - events[-1].end < Settings.EVENT_MERGE_TIME:

            events[-1].end = now

            where_start = np.searchsorted(timestamps, events[-1].start)
            
            events[-1].data = buffer[where_start : -1]

            if events[-1].data.shape[0] > Settings.BUFFER_LENGTH // 2:

                end_event(events[-1], buffer, timestamps)

        else:
            # Cannot merge event make new one

            # Check if length is less certain amount kill event
            if events[-1].data.shape[0] < Settings.MIN_EVENT_LENGTH:
                events.pop()
            else:

                end_event(events[-1], buffer, timestamps)

            events.append(
                Anomaly(
                    start=now,
                    end=now,
                    data=buffer[-1],
                    sensors=sensors,
                )
            )

    # Remove stale events
    elif events and not events[-1].final and now - events[-1].end > Settings.EVENT_MERGE_TIME:

        end_event(events[-1], buffer, timestamps)

