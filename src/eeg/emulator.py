import time, random

from .data import load_data
from .schema import DataPoint

def emulate_event_emission(classification: str) -> DataPoint:

    data = load_data('~/neurom-backend/data_store/examples.json')

    time.sleep(1)

    return random.choice([d for d in data if d.classification == classification])