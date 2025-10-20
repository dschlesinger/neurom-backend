import keybinding.model

from typing import List

def emit_keybind(events: List[str], max_que_length: int = 5) -> bool:
    """Returns true if finds keybind or hit limit else false"""
    print(events.__len__())

    print(keybinding.model.model.predict(events[-1]))