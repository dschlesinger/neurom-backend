import json
import os
import math
from dataclasses import dataclass
from itertools import groupby

from dtaidistance import dtw
import numpy as np
from sklearn.decomposition import PCA

from pydantic import BaseModel, ConfigDict, PrivateAttr
from typing import List, Optional

from eeg.schema import Anomaly, DataPoint
from cli.config import Settings
from keybinding.algorithms import (
    AlgorithmBase,
    create_algorithm,
    pad_center,
    pad_or_trim_center,
)

class NoDatasetLoaded(Exception):
    pass

model = None

def pad_center(d: List[np.ndarray], max_len: int | None = None) -> np.ndarray:

    # Normalize to (channels, time)
    d = [np.array(di).T for di in d]

    max_len = max(*[di.shape[1] for di in d], max_len or 0)

    padded = []

    for di in d:

        pad_needed = max_len - di.shape[1]

        left_pad, right_pad = pad_needed // 2, math.ceil(pad_needed / 2)

        p = np.pad(di, ((0, 0), (left_pad, right_pad)), mode='mean')

        padded.append(p)

    return np.array(padded)

@dataclass
class TrainState:
    algorithm: AlgorithmBase
    max_len: int
    pca: Optional[PCA]

class Model(BaseModel):
    """Dynamic Time Warp based on previous data points"""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    datapoints: Optional[List[DataPoint]] = None

    current_datasets: List[str] = []

    algorithm_name: str = Settings.ALGORITHM_NAME
    _train_state: Optional[TrainState] = PrivateAttr(default=None)
    
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
        self._train_state = self._prepare_training(datapoints)

    def get_all_classifications(self) -> List[str]:

        if self.datapoints is None:
            return []

        return list(set([d.classification for d in self.datapoints]))

    def get_all_datasets(self) -> List[str]:

        return os.listdir('data_store')
    
    def test_on_data(self) -> List:

        tr = []

        for d in self.datapoints:

            p = self.predict(d.anom, exclude=d)
        
            tr.append({
                'guess': p,
                'correct': d.classification,
            })

        return tr
        
    def predict(self, artifact: Anomaly, exclude: DataPoint | None = None) -> str:
        
        if self.datapoints is None:
            
            print('No Dataset Loaded')
            return
        
        if exclude is not None:
            avail_data = [dp for dp in self.datapoints if dp != exclude]
            train_state = self._prepare_training(avail_data)
        else:
            avail_data = self.datapoints
            train_state = self._train_state

        if train_state is None:
            raise NoDatasetLoaded("No training data available")

        x = artifact.data.T
        x = pad_or_trim_center(x, train_state.max_len)
        
        classes = [dp.classification for dp in avail_data]
        
        w = pad_center([dp.anom.data for dp in avail_data], max_len=x.shape[1])
        
        if w.shape[2] > x.shape[1]:
            # Pad x to reach w
            diff = w.shape[2] - x.shape[1]
        
            left_pad, right_pad = diff // 2, math.ceil(diff / 2)
            
            x = np.pad(x, ((0, 0), (left_pad, right_pad)), mode='mean')
            
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

        if train_state.algorithm.input_type == "window":
            return train_state.algorithm.predict(x)

        flat = x.reshape(-1)
        if train_state.pca is not None:
            flat = train_state.pca.transform([flat])[0]
        return train_state.algorithm.predict(flat)

    def _prepare_training(self, datapoints: List[DataPoint]) -> Optional[TrainState]:
        if not datapoints:
            return None

        labels = [dp.classification for dp in datapoints]
        windows = pad_center([dp.anom.data for dp in datapoints])
        max_len = windows.shape[2]

        features = windows.reshape(windows.shape[0], -1)
        pca = None

        if Settings.PCA_ENABLE:
            max_components = min(Settings.PCA_COMPONENTS, features.shape[0], features.shape[1])
            if max_components > 0:
                pca = PCA(n_components=max_components)
                features = pca.fit_transform(features)

        params = {
            "band": Settings.CONSTRAINED_DTW_BAND,
        }

        algorithm = create_algorithm(self.algorithm_name, params)
        if algorithm.input_type == "window":
            algorithm.fit(windows, labels)
        else:
            algorithm.fit(features, labels)

        return TrainState(algorithm=algorithm, max_len=max_len, pca=pca)
    
model = Model()
# model.load_data(['./data_store/examples.json'])