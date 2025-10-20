import numpy as np, json, math, scipy, matplotlib.pyplot as plt

from itertools import groupby
from dtaidistance import dtw

from pydantic import BaseModel
from typing import List, Optional

from eeg.schema import Anomaly, DataPoint

class NoDatasetLoaded(Exception):
    pass

def pad_center(d: List[np.ndarray], max_len: int | None = None) -> np.ndarray:

    # Could be a memory view
    d = [np.array(di).T for di in d]
    
    max_len = max(*[di.data.shape[1] for di in d], max_len or 0)

    padded = []

    print(max_len)
    
    for di in d:
        
        pad_needed = max_len - di.data.shape[1]
            
        left_pad, right_pad = pad_needed // 2, math.ceil(pad_needed / 2)
        
        p = np.pad(di.data, ((0, 0), (left_pad, right_pad)), mode='mean')
        
        padded.append(p)
        
    return np.array(padded)

model = None

class Model(BaseModel):
    """Dynamic Time Warp based on previous data points"""
    
    datapoints: Optional[List[DataPoint]] = None

    current_datasets: List[str] = []
    
    @property
    def dataset_loaded(self) -> bool:
        return self.datapoints is not None
    
    def load_data(self, filepaths: List[str]) -> None:

        self.current_datasets = filepaths
        
        datapoints = []
        
        for f in filepaths:
            with open(f, 'r') as e:
                rd = json.load(e)
                for dp in rd:
                    
                    an = dp['anom']
                    
                    a = Anomaly(
                        start=an['start'],
                        end=an['end'],
                        data=np.array(an['data']),
                        final=True,
                        sensors=an['sensors'],
                    )
                    
                    d = DataPoint(
                        classification=dp['classification'],
                        anom=a
                    )
                    
                    datapoints.append(d)
                
        self.datapoints = datapoints

    def get_all_classifications(self) -> List[str]:

        if self.datapoints is None:
            return []

        return list(set([d.classification for d in self.datapoints]))
        
    def predict(self, artifact: Anomaly) -> str:
        
        if self.datapoints is None:
            
            raise NoDatasetLoaded
        
        x = artifact.data
        
        classes = [dp.classification for dp in self.datapoints]
        
        w = pad_center([dp.anom.data for dp in self.datapoints], max_len=x.shape[1])
        
        if w.shape[1] > x.shape[1]:
            # Pad x to reach w
            diff = w.shape[1] - x.shape[1]
        
            left_pad, right_pad = diff // 2, math.ceil(diff / 2)
            
            x = np.pad(x, ((left_pad, right_pad)), mode='mean')
            
        values = []
        
        for di in w:
            
            values.append(sum([dtw.distance_fast(xi, di) for xi, di in zip(x, di)]))
            
        cls_choice = []
        cls_values = []
        
        z = sorted(list(zip(values, classes)), key=lambda a: a[1])
            
        for c, vls in groupby(z, key=lambda a: a[1]):
            
            vls = [v[0] for v in list(vls)]
            
            cls_choice.append(c)
            cls_values.append(sum(vls) / len(vls))

        a = np.array(cls_values)
        
        a = (a - a.mean()) / a.std()
        
        probs = scipy.special.softmax(-a)

        # print(probs)
        fig, axs = plt.subplots(5)

        for a, xi in zip(axs, x):

            a.plot(xi)

        plt.savefig(f'edebug/event{artifact.start}.png')
        
        for pro, cls in zip(probs, cls_choice):
            
            print(f'\t{cls}: {pro.item():.2f}')
        
        return cls_choice[probs.argmin().item()]
    
model = Model()
model.load_data(['./data_store/examples.json'])