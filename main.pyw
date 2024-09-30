import tkinter as tk
import csv
try: from pygame import mixer # TODO: Fix this issue
except ModuleNotFoundError: pass
from datetime import datetime, timedelta
from enum import Enum
import logging.config
from json import load
from ctypes import windll
from typing import Iterator
from pathlib import Path

DEBUG_MODE = False #########################################

DEFAULT_ALPHA: float = 0.95
HIDING_ALPHA: float = 0.20
STOPWATCH_FONT: tuple[str, int, str] = ('Arial', 50, 'normal')
STOPWATCH_BACKGROUND: str = '#282828'
LABEL_PAUSED_COLOUR: str = 'grey'
LABEL_RUNNING_COLOUR: str = 'white'
LABEL_BREAKING_COLOUR: str = '#2ecc71' # green
LABEL_STOPPED_COLOUR: str = '#e74c3c' # red
LONG_BREAK_DIVISOR: float = 3.5
SHORT_BREAK_DIVISOR: float = 5
BREAK_CUTOFF_SECONDS: float = 5 * 60 # You need to have studied at least that many seconds to start a break.
MESSAGES: list[str] = ['Bitte trinkt wasser', 'Go outside, eat an apple, and touch grass or something']

BASE_DIR = Path(__file__).parent
LOGGING_CONFIG_PATH = BASE_DIR / "data" / "logging_config.json"
PROGRESS_CSV_PATH = BASE_DIR / "data" / "progress.csv"
BREAK_OVER_SOUND_PATH = BASE_DIR / "assets" / "wine-glass-alarm.ogg"
ERROR_SOUND_PATH = BASE_DIR / "assets" / "windows-xp-error.mp3"

windll.shcore.SetProcessDpiAwareness(1) # Makes the font look cleaner using anti-alliasing probably.
# Also changes my window size for some reason; I was wondering why suddenly switching to classes made my stopwatch look weirder.
# Also... I am using windll as an object; but VScode tells me it's a variable?

with open(LOGGING_CONFIG_PATH, 'r') as config_file:
    logging.config.dictConfig(load(config_file))
logger = logging.getLogger(__name__)


class WTFError(Exception):
    def __init__(self, *args, **kwargs):
        logger.info(repr(args))
        logger.info(repr(kwargs))
        play_sound(ERROR_SOUND_PATH)


class State(Enum):
    PAUSED = 0 # Default. Starts here only. No need for an UNINITIALISED state.
    RUNNING = 1
    BREAKING = 3
    STOPPED = 4 # break timer goes to 0


class Stopwatch(tk.Tk):
    # __slots__ = 'state', 'hiding', 'start_time', 'label', 'x', 'y'
    # Run mypy with strict mode on before enabling the above.
    # https://mypy.readthedocs.io/en/stable/getting_started.html
    # https://marketplace.visualstudio.com/items?itemName=ms-python.mypy-type-checker
    
    def __init__(self, *args, **kwargs) -> None:
        logger.info('Stopwatch initialised.')

        tk.Tk.__init__(self, *args, **kwargs)
        self.overrideredirect(True) # Rips out the titlebar
        self.config(bg=STOPWATCH_BACKGROUND)
        self.alpha: float = DEFAULT_ALPHA
        self.attributes('-alpha', self.alpha)
        self.attributes('-topmost', True)
        self.minsize(width=250, height=80)
        self.geometry('+0+800')

        self.label: tk.Label = tk.Label(
            self,
            text='~00~',
            foreground=LABEL_PAUSED_COLOUR,
            font=STOPWATCH_FONT,
            bg=STOPWATCH_BACKGROUND
        ) 
        self.label.pack()

        self.state: State = State.PAUSED
        self.hiding: bool = False
        self.start_time: datetime = datetime.now()
        self.running_time: timedelta = timedelta()
        self.remaining_break_time: timedelta = timedelta()
        self.bind_everything()
        if DEBUG_MODE: self.start_stop()

    def bind_everything(self) -> None:
        def Keypress(event):
            if event.char == ' ':
                self.start_stop()
            elif event.char == 'h':
                self.hide()
        self.bind('<Key>', Keypress)
        self.bind('<Shift_L><Shift_R>', (lambda event: self.start_stop_break()))
        self.bind('<Right>', (lambda event: self.fast_forward()))
        self.bind('<Left>', (lambda event: self.rewind()))
        self.bind('<Control_L><Left>', (lambda event:self.reset()))
        self.bind('<Escape>', (lambda event: self.kill()))

        self.x = 0
        self.y = 0
        self.bind('<Button-1>', self.click)
        self.bind('<B1-Motion>', self.drag)
        self.bind('<Enter>', (lambda event: self.hover()))
        self.bind('<Leave>', (lambda event: self.mouse_leave()))
    
    def click(self, event) -> None:
        self.x = event.x
        self.y = event.y
        self.attributes('-alpha', self.alpha-0.15)

    def drag(self, event) -> None:
        x = event.x - self.x + self.winfo_x()
        y = event.y - self.y + self.winfo_y()
        self.geometry("+%s+%s" % (x , y))
        self.attributes('-alpha', self.alpha-0.15)

    def mouse_leave(self) -> None:
        self.attributes('-alpha', self.alpha)
    
    def hover(self) -> None:
        self.attributes('-alpha', self.alpha-0.15)

    def hide(self) -> None:
        if self.hiding:
            self.alpha = DEFAULT_ALPHA
        else:
            self.alpha = HIDING_ALPHA
        self.attributes('-alpha', self.alpha)
        self.hiding = not self.hiding

    def start_stop(self) -> None:
        match self.state:
            case State.PAUSED | State.STOPPED:
                self.state = State.RUNNING
                self.label.config(fg=LABEL_RUNNING_COLOUR)
                self.start_time = datetime.now() - self.running_time
                self.run()
            case State.RUNNING:
                self.state = State.PAUSED
                self.label.config(fg=LABEL_PAUSED_COLOUR)
                self.update_display()
            case State.BREAKING:
                # Not allowed to pause in a breaking state. Feature, not a bug!
                play_sound(ERROR_SOUND_PATH)
            case _:
                raise WTFError(f'the state isn\'t supposed to be {self.state} wtf is this shit you stupid fucking cunt delete urself')
    
    # TODO: Handle all switch states with a switch state function, which automatically changes the colour of the label as well?

    def start_stop_break(self) -> None:
        match self.state:
            case State.BREAKING: # TODO: Cancel break and start studying again
                self.state = State.RUNNING
                self.update_display()
            case State.STOPPED:
                play_sound(ERROR_SOUND_PATH)
            case _:
                if self.running_time.total_seconds() < BREAK_CUTOFF_SECONDS:
                    play_sound(ERROR_SOUND_PATH)
                    return
                
                if self.running_time.total_seconds() >= 50*60:
                    self.remaining_break_time = self.running_time / LONG_BREAK_DIVISOR
                else:
                    self.remaining_break_time = self.running_time / SHORT_BREAK_DIVISOR

                self.start_time = datetime.now()
                if self.state == State.PAUSED:
                    self.state = State.BREAKING
                    self.run()
                else:
                    self.state = State.BREAKING
                self.label.config(fg=LABEL_BREAKING_COLOUR)
                self.log(self.remaining_break_time)
                self.message()

    def run(self) -> None:
        if self.state == State.RUNNING:
            self.update_display()
        elif self.state == State.BREAKING:
            self.update_break_display()
        # TODO: Maybe use a match statement instead, and automatically start running if state is PAUSED; should eliminate boilerplate?
        self.after(100, self.run)

    def update_display(self) -> None:
        self.running_time = datetime.now() - self.start_time
        self.label.config(text=self.format_count(self.running_time))

    def update_break_display(self) -> None:
        t: timedelta = datetime.now() - self.start_time
        if t >= self.remaining_break_time:
            self.label.config(fg=LABEL_STOPPED_COLOUR, text=self.format_count(timedelta()))
            self.state = State.STOPPED
            play_sound(BREAK_OVER_SOUND_PATH)
            self.remaining_break_time = timedelta()
            return
        self.label.config(text=self.format_count(self.remaining_break_time - t))

    @staticmethod
    def format_count(t: timedelta) -> str:
        if t.days < 0:
            return 'ẽ̸̛̝̘͈͔͓͇̓͗̒̀͐̄̒̄̏̄͘͜͜͝͝͠͝ͅR̶͉͙̹̩̘̳̯̜̘͉̯̠̾̑̐́̊̂͗͑͐͑̅̕̕R̴͕͍̓0̸̢̡̭͚̟̫̓̆̊͠R̸̤̗̘̻͒̃̈̃̓̊̐̀̎̊͋̚' # fnuny
        
        if DEBUG_MODE:
            return str(int(t.total_seconds() // 1))
        minutes = int(t.total_seconds() // 60)
        if minutes <= 9:
            return f"0{minutes}"
        return str(minutes)
    
    @staticmethod
    def log(t: timedelta) -> None:
        if DEBUG_MODE:
            logger.info(f"Break with {t.total_seconds()} seconds initialised.")
        with open(PROGRESS_CSV_PATH, 'w') as csvf:
            writer: Iterator = csv.writer(csvf, delimiter=',')
            writer.writerow((datetime.now().isoformat(), f"{t.total_seconds()}"))
    
    def message(self) -> None: # TODO: If this function turns out to be small enough, just fit it in start_stop_break
        pass
        # Message(self).mainloop()
    
    def fast_forward(self) -> None:
        match self.state:
            case State.RUNNING | State.PAUSED:
                self.start_time -= timedelta(seconds=10)
                self.update_display()
            case State.BREAKING:
                self.start_time += timedelta(seconds=10)

    def rewind(self) -> None:
        match self.state:
            case State.RUNNING | State.PAUSED:
                if self.running_time.total_seconds() < 10:
                    self.start_time += self.running_time
                else:
                    self.start_time += timedelta(seconds=10)
                self.update_display()
            case State.BREAKING:
                self.start_time -= timedelta(seconds=10)
    
    def reset(self) -> None:
        self.start_time = datetime.now()
        self.update_display()

    def kill(self) -> None:
        if self.state == State.BREAKING:
            t: timedelta = self.remaining_break_time
        else:
            t: timedelta = self.running_time
        logger.info(f"Stopwatch killed using `Esc` with {t} seconds on the clock. Best of luck with everything.")
        self.destroy()


"""
class Message(tk.Toplevel):
    # The message should be small and somewhere on the lower right corner of the screen.
    # Use MESSAGES = [...] which is defined globally.

    def __init__(self, master, *args, **kwargs) -> None:
        tk.Toplevel.__init__(master, *args, **kwargs)
"""


def play_sound(sound_path) -> None:
    try:
        mixer.init()
        mixer.music.load(sound_path)
        mixer.music.set_volume(1)
        mixer.music.play()
    except Exception as message:
        logger.error(message)


def main() -> None:
    Stopwatch().mainloop()


if __name__ == '__main__':
    main()


# FEATURES:
# - Maybe resize ability?
# - If stopwatch is launched through VScode, it runs in DEBUG mode, where records are not added to progress_v2.csv but the logger instead.

# INSPIRATIONS:
# - https://gitlab.com/-/snippets/2376113
# - https://github.com/SqrtNegativOne/databaseprojectthing/blob/main/main.py/
# - https://www.reddit.com/r/learnpython/comments/mgp7en/tkinter_toplevel_duplicate_instances/