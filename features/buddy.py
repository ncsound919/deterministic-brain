from __future__ import annotations
"""
BUDDY — Companion sprite / terminal personality.

Renders a small ASCII companion in the terminal that reacts to
brain state: thinking, success, error, idle. Also provides
encouraging messages and personality responses.
"""
import random

_SPRITES = {
    'idle':     ['(=^.^=)', '( ◕ • ◕ )', '(•ᴥ•)'],
    'thinking': ['(*  ◡  *)', '(= o_o =)', '(¬•‿•¬)'],
    'success':  ['(=^___^=)', '(\u25c9‿◉)', '( •ᴥ• )╯︵ ┻━┻'],
    'error':    ['(T_T)', '(x_x)', '(>_<)'],
    'working':  ['( ◔ ◡ ◕ )', '(oUo)', '(*•́ᴥ•̀*)'],
}

_MESSAGES = {
    'idle':     ['Ready when you are!', 'What shall we solve today?', 'Standing by...'],
    'thinking': ['Hmm, let me think...', 'Processing...', 'Reasoning step by step...'],
    'success':  ['Nailed it!', 'Done! That felt good.', 'Confidence: high!'],
    'error':    ['Oops, let me try again.', 'That was tricky...', 'Retrying with a fresh approach.'],
    'working':  ['On it!', 'Running the lanes...', 'Engaging MCTS...'],
}


def render(state: str = 'idle') -> str:
    sprite  = random.choice(_SPRITES.get(state, _SPRITES['idle']))
    message = random.choice(_MESSAGES.get(state, _MESSAGES['idle']))
    return f'{sprite}  {message}'


def animate_thinking(steps: int = 3) -> list[str]:
    return [render('thinking') for _ in range(steps)]
