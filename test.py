import keybinding.handler

from time import sleep

sleep(3)

keybinding.handler.keybindings = [
    {
        'ordered_artifacts': ['Single Blink'],
        'keybind': {
            'hold': False,
            'keys': [['space']]
        },
        'reset': False
    },
]

keybinding.handler.emit_keybind(['Single Blink'])