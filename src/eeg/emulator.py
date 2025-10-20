import time, random

import eeg.data
from .schema import DataPoint

def emulate_event_emission(classification: str) -> DataPoint:

    data = eeg.data.load_data('data_store/examples.json')

    time.sleep(1)

    c = random.choice([d for d in data if d.classification == classification])

    eeg.data.datapoints.append(c)

    return c