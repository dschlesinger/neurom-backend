import keybinding.model
from typing import List, Set
import threading
import time
import sys


class KeybindBackend:
    def click(self) -> None:
        raise NotImplementedError

    def right_click(self) -> None:
        raise NotImplementedError

    def move_rel(self, x: int, y: int) -> None:
        raise NotImplementedError

    def key_down(self, key: str) -> None:
        raise NotImplementedError

    def key_up(self, key: str) -> None:
        raise NotImplementedError

    def press(self, keys: List[str]) -> None:
        raise NotImplementedError


class PyDirectInputBackend(KeybindBackend):
    def __init__(self) -> None:
        import pydirectinput as p
        self._p = p

    def click(self) -> None:
        self._p.click()

    def right_click(self) -> None:
        self._p.rightClick()

    def move_rel(self, x: int, y: int) -> None:
        self._p.moveRel(x, y)

    def key_down(self, key: str) -> None:
        self._p.keyDown(key)

    def key_up(self, key: str) -> None:
        self._p.keyUp(key)

    def press(self, keys: List[str]) -> None:
        self._p.press(keys)


class PynputBackend(KeybindBackend):
    def __init__(self) -> None:
        from pynput.keyboard import Controller as KeyboardController, Key
        from pynput.mouse import Controller as MouseController, Button

        self._keyboard = KeyboardController()
        self._mouse = MouseController()
        self._Key = Key
        self._Button = Button

    def _to_key(self, key: str):
        mapping = {
            'up': self._Key.up,
            'down': self._Key.down,
            'left': self._Key.left,
            'right': self._Key.right,
            'enter': self._Key.enter,
            'space': self._Key.space,
            'tab': self._Key.tab,
            'esc': self._Key.esc,
            'escape': self._Key.esc,
            'backspace': self._Key.backspace,
            'delete': self._Key.delete,
            'shift': self._Key.shift,
            'ctrl': self._Key.ctrl,
            'alt': self._Key.alt,
            'caps_lock': self._Key.caps_lock,
            'home': self._Key.home,
            'end': self._Key.end,
            'pageup': self._Key.page_up,
            'pagedown': self._Key.page_down,
            'insert': self._Key.insert,
            'menu': self._Key.menu,
            'cmd': self._Key.cmd,
            'win': self._Key.cmd,
        }
        return mapping.get(key, key)

    def click(self) -> None:
        self._mouse.click(self._Button.left, 1)

    def right_click(self) -> None:
        self._mouse.click(self._Button.right, 1)

    def move_rel(self, x: int, y: int) -> None:
        self._mouse.move(x, y)

    def key_down(self, key: str) -> None:
        self._keyboard.press(self._to_key(key))

    def key_up(self, key: str) -> None:
        self._keyboard.release(self._to_key(key))

    def press(self, keys: List[str]) -> None:
        for key in keys:
            mapped = self._to_key(key)
            self._keyboard.press(mapped)
            self._keyboard.release(mapped)


def _select_backend() -> KeybindBackend:
    if sys.platform == 'win32':
        try:
            return PyDirectInputBackend()
        except ImportError as exc:
            raise RuntimeError('PyDirectInput is required on Windows for keybindings.') from exc

    try:
        return PynputBackend()
    except ImportError as exc:
        raise RuntimeError('pynput is required on Linux/macOS for keybindings.') from exc


backend = _select_backend()

keybindings = []
keysdown: Set[str] = set()
functional_held: Set[str] = set()
hold_threads = {}
stop_hold_events = {}

# Map JavaScript key names to Python key names
JS_KEYS_TO_PY = {
    'ArrowUp': 'up',
    'ArrowDown': 'down',
    'ArrowLeft': 'left',
    'ArrowRight': 'right',
}

# Functional keybinds that don't use keyboard keys
FUNCTIONAL_KBS = {
    'Left Click': lambda: backend.click(),
    'Right Click': lambda: backend.right_click(),
    'Mouse Up': lambda: backend.move_rel(0, -100),
    'Mouse Down': lambda: backend.move_rel(0, 100),
    'Mouse Right': lambda: backend.move_rel(100, 0),
    'Mouse Left': lambda: backend.move_rel(-100, 0),
    'Slight Mouse Up': lambda: backend.move_rel(0, -30),
    'Slight Mouse Down': lambda: backend.move_rel(0, 30),
    'Slight Mouse Right': lambda: backend.move_rel(30, 0),
    'Slight Mouse Left': lambda: backend.move_rel(-30, 0),
}


def normalize_key(key: str) -> str:
    """Convert JavaScript key names to Python key names."""
    return JS_KEYS_TO_PY.get(key, key)


def release_all_keys() -> None:
    """Release all currently held keys and stop all functional holds."""
    for key in list(keysdown):
        backend.key_up(normalize_key(key))
    keysdown.clear()
    
    # Stop all functional holds
    for func_key in list(functional_held):
        stop_functional_hold(func_key)


def hold_functional_loop(func_key: str, interval: float = 0.1) -> None:
    """Repeatedly execute a functional keybind until stopped."""
    stop_event = stop_hold_events[func_key]
    func = FUNCTIONAL_KBS[func_key]
    
    while not stop_event.is_set():
        func()
        time.sleep(interval)


def start_functional_hold(func_key: str, interval: float = 0.1) -> None:
    """Start holding a functional keybind (repeated execution)."""
    if func_key in functional_held:
        return
    
    functional_held.add(func_key)
    stop_hold_events[func_key] = threading.Event()
    
    thread = threading.Thread(target=hold_functional_loop, args=(func_key, interval), daemon=True)
    hold_threads[func_key] = thread
    thread.start()


def stop_functional_hold(func_key: str) -> None:
    """Stop holding a functional keybind."""
    if func_key not in functional_held:
        return
    
    functional_held.discard(func_key)
    
    if func_key in stop_hold_events:
        stop_hold_events[func_key].set()
        
    if func_key in hold_threads:
        hold_threads[func_key].join(timeout=0.5)
        del hold_threads[func_key]
        del stop_hold_events[func_key]


def toggle_hold_key(key: str) -> None:
    """Toggle a key between held and released states."""
    normalized_key = normalize_key(key)
    
    if key in keysdown:
        backend.key_up(normalized_key)
        keysdown.discard(key)
    else:
        backend.key_down(normalized_key)
        keysdown.add(key)


def toggle_hold_functional(func_key: str) -> None:
    """Toggle a functional keybind between held (repeating) and released states."""
    if func_key in functional_held:
        stop_functional_hold(func_key)
    else:
        start_functional_hold(func_key)


def execute_press_keybind(key_sequences: List[List[str]]) -> None:
    """Execute a press-style keybind with support for key sequences and functional keys."""
    for sequence in key_sequences:
        # Separate functional keys from regular keys
        functional_keys = [k for k in sequence if k in FUNCTIONAL_KBS]
        regular_keys = [k for k in sequence if k not in FUNCTIONAL_KBS]
        
        # Execute functional keys once
        for func_key in functional_keys:
            FUNCTIONAL_KBS[func_key]()
        
        # Press regular keys if any exist
        if regular_keys:
            normalized_keys = [normalize_key(k) for k in regular_keys]
            print('Pressing:', normalized_keys)
            backend.press(normalized_keys)


def execute_hold_keybind(key_sequences: List[List[str]]) -> None:
    """Execute a hold-style keybind with support for functional keys."""
    for sequence in key_sequences:
        for key in sequence:
            if key in FUNCTIONAL_KBS:
                toggle_hold_functional(key)
            else:
                toggle_hold_key(key)


def emit_keybind(events: List[str], max_queue_length: int = 5) -> bool:
    """
    Process events and emit keybinds if matched.
    
    Args:
        events: List of event names to match against keybindings
        max_queue_length: Maximum length of event queue before forcing a reset
    
    Returns:
        True if a keybind was found/executed or the queue limit was hit, False otherwise
    """
    print('Events:', events)
    
    # Check queue length limit
    if len(events) > max_queue_length:
        return True
    
    # Check if keybindings are configured
    if not keybindings:
        print('No keybindings set')
        return True
    
    found_possible = False
    
    for kb in keybindings:
        # Exact match - execute the keybind
        if kb['ordered_artifacts'] == events:
            
            # Reset mode - release all held keys
            if kb['reset']:
                release_all_keys()
                return True
            
            # Hold mode - toggle key states
            elif kb['keybind']['hold']:
                execute_hold_keybind(kb['keybind']['keys'])
                return True
            
            # Press mode - execute key presses
            else:
                execute_press_keybind(kb['keybind']['keys'])
                return True
        
        # Partial match - there's still a possible keybind
        elif kb['ordered_artifacts'][:len(events)] == events:
            found_possible = True
    
    # Return False if we found a possible match (keep waiting for more events)
    # Return True if no possible matches (reset the queue)
    return not found_possible