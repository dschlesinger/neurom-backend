from dataclasses import dataclass

from typing import List, Callable, Literal

@dataclass
class MuseStatusManager:

    stream_started: bool = False
    muse_has_buffered: bool = False
    status: Literal['not connected', 'not buffered', 'ready'] = 'not connected'
    
    def set_status(self, stream_started: bool | None = None, muse_has_buffered: bool | None = None) -> None:
                
        if stream_started is not None:
            self.stream_started = stream_started
            
        if muse_has_buffered is not None:
            self.muse_has_buffered = muse_has_buffered
            
        status: str = 'not connected'
        
        if self.stream_started and self.muse_has_buffered:
            status = 'ready'
            
        elif self.stream_started:
            status = 'not buffered'
            
        if self.status != status:
            print(f'New status {status}')
            
            self.status = status
                
status_manager = MuseStatusManager()