import json

from .schema import DataPoint

from typing import List

def load_data(file: str) -> List[DataPoint]:

    with open(file, 'r') as j:

        return [DataPoint(**d) for d in json.load(j)] 