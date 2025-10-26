import keybinding.model
from typing import List, Set, Callable
import threading
import time

try:
    import pydirectinput as p
except ImportError:
    import pyautogui as p

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
    'Left Click': lambda: p.click(),
    'Right Click': lambda: p.rightClick(),
    'Mouse Up': lambda: p.moveRel(0, -100),
    'Mouse Down': lambda: p.moveRel(0, 100),
    'Mouse Right': lambda: p.moveRel(100, 0),
    'Mouse Left': lambda: p.moveRel(-100, 0),
    'Slight Mouse Up': lambda: p.moveRel(0, -30),
    'Slight Mouse Down': lambda: p.moveRel(0, 30),
    'Slight Mouse Right': lambda: p.moveRel(30, 0),
    'Slight Mouse Left': lambda: p.moveRel(-30, 0),
}


def normalize_key(key: str) -> str:
    """Convert JavaScript key names to Python key names."""
    return JS_KEYS_TO_PY.get(key, key)


def release_all_keys() -> None:
    """Release all currently held keys and stop all functional holds."""
    for key in list(keysdown):
        p.keyUp(normalize_key(key))
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
        p.keyUp(normalized_key)
        keysdown.discard(key)
    else:
        p.keyDown(normalized_key)
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
            p.press(normalized_keys)


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