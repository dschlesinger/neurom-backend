import keybinding.model

from typing import List

try:
    import pydirectinput as p
except ImportError:
    import pyautogui as p

keybindings = []

keysdown = set()

def emit_keybind(events: List[str], max_que_length: int = 5) -> bool:
    """Returns true if finds keybind or hit limit else false"""

    # no future matches
    fut_match = False

    print(events)

    if len(events) > max_que_length:
        return True
    
    if not keybinding:
        print('No Keybindings set')
        return True
    
    for kb in keybindings:

        if kb['ordered_artifacts'] == events:
            # We should emit a keybind

            # Reset everything
            if kb['reset']:

                for kd in keysdown:

                    p.keyUp(kd)

                return True

            elif kb['keybind']['hold']:
                
                # Assume with one with all
                if kb['keybind']['keys'][0][0] not in keysdown:

                    p.keyDown(kb['keybind']['keys'][0])

                    for k in kb['keybind']['keys'][0]:

                        keysdown.add(k)
                
                else:

                    p.keyUp(kb['keybind']['keys'][0])

                    for k in kb['keybind']['keys'][0]:

                        keysdown.remove(k)

            else:

                for s in kb['keybind']['keys']:

                    p.press(s)
                
            return True
        
        elif kb['ordered_artifacts'] == events[0:len(kb['ordered_artifacts'])]:

            # There are potential future matches
            fut_match = True

    return not fut_match
