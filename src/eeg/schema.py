import json, numpy as np

from pydantic import BaseModel, ConfigDict, model_serializer, \
    model_validator, field_serializer

from typing import Dict, Self, List

class Anomaly(BaseModel):

    # Timestamps
    start: float
    end: float

    # Make sure not deltas
    data: np.ndarray

    sensors: List[str]

    # If no more changes to event
    final: bool = False

    model_config = ConfigDict(arbitrary_types_allowed=True, validate_assignment=True)
    
    @model_serializer
    def ser(self) -> Dict:

        print('Ser runs')

        return {
            'start': self.start,
            'end': self.end,
            'data': self.data.tolist(),
            'sensors': self.sensors,
            'final': self.final
        }
 
    @model_validator(mode='before')
    def convert_numpy(cls, value: Dict) -> Self:

        value['data'] = np.array(value['data'])
        
        return value
        

class DataPoint(BaseModel):

    classification: str | None
    anom: Anomaly
    
    @model_serializer(mode='plain')
    def model_ser(self) -> Dict:
        return {
            'anom': self.anom.model_dump(),
            'classification': self.classification,
        } 

    @model_validator(mode='before')
    def init_anom(cls, value: Dict) -> Self:

        value['anom'] = Anomaly(**value['anom'])
        
        return value
        
if __name__ == '__main__':

    with open('~/neurom-backend/data_store/examples.json', 'r') as j:

        data = [d for d in json.load(j)]



    data = [DataPoint(**d) for d in data]