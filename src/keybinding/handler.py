import keybinding.model

from typing import List

try:
    import pydirectinput as p
except ImportError:
    import pyautogui as p

keybindings = []

keysdown = set()

js_keys_to_py = {
    'ArrowUp': 'up',
    'ArrowDown': 'down',
    'ArrowLeft': 'left',
    'ArrowRight': 'right',
}

def emit_keybind(events: List[str], max_que_length: int = 5) -> bool:
    """Returns true if finds keybind or hit limit else false"""

    print(events)

    found_possible: bool = False

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

                    if kd in js_keys_to_py:
                        kd = js_keys_to_py[kd]

                    p.keyUp(kd)

                return True

            elif kb['keybind']['hold']:
                
                # Assume with one with all
                if kb['keybind']['keys'][0][0] not in keysdown:

                    if kb['keybind']['keys'][0][0] in js_keys_to_py:
                        kd = js_keys_to_py[kb['keybind']['keys'][0][0]]
                    else:
                        kd = kb['keybind']['keys'][0][0]

                    p.keyDown(kd)

                    keysdown.add(kd)
                
                else:

                    if kb['keybind']['keys'][0][0] in js_keys_to_py:
                        kd = js_keys_to_py[kb['keybind']['keys'][0][0]]
                    else:
                        kd = kb['keybind']['keys'][0][0]

                    p.keyUp(kd)

                    keysdown.remove(kd)

            else:

                for s in kb['keybind']['keys']:
                    
                    s = [js_keys_to_py.get(si, si) for si in s]

                    print('Doing', s)

                    p.press(s)
                
            return True
        
        elif kb['ordered_artifacts'][:len(events)] == events:

            found_possible = True
        
    return not found_possible
