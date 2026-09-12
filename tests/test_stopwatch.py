import threading
from types import SimpleNamespace

import termdown.modes as modes
from termdown.events import INPUT_EXIT, INPUT_PAUSE, INPUT_RESET, TIME_TICK


class FakeClock:
    """Controllable stand-in for time.monotonic()."""

    def __init__(self, start=1000.0):
        self.now = start

    def monotonic(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


def make_metronome(clock):
    """Returns a Metronome replacement that tracks pause state on `clock`."""

    class FakeMetronome:
        def __init__(self, queue, offset=0):
            self.queue = queue
            self._paused_at = None

        def start(self):
            pass

        def pause(self):
            if self._paused_at is not None:
                duration = clock.monotonic() - self._paused_at
                self._paused_at = None
                return duration
            self._paused_at = clock.monotonic()
            return None

        @property
        def is_paused(self):
            return self._paused_at is not None

    return FakeMetronome


class ScriptedQueue:
    """input_queue replacement that advances the clock on every get()."""

    def __init__(self, script, clock):
        self._script = list(script)
        self._clock = clock
        self._index = 0

    def get(self, *args, **kwargs):
        advance, event = self._script[self._index]
        self._index += 1
        self._clock.advance(advance)
        return event

    def put(self, item):
        pass


class RecordingUi:
    def __init__(self, script, clock):
        self.curses_lock = threading.Lock()
        self.input_queue = ScriptedQueue(script, clock)
        self.texts = []

    def draw_text(self, text, color=0, end=None):
        self.texts.append(text)

    def set_window_title(self, text):
        pass


ARGS = SimpleNamespace(
    quit_after=None,
    alt_format=False,
    no_seconds=False,
    no_window_title=True,
    outfile=None,
    critical=3,
    voice_prefix="",
    voice_cmd=None,
    exec_cmd=None,
)


def run_stopwatch(monkeypatch, script):
    clock = FakeClock()
    monkeypatch.setattr(modes, "monotonic", clock.monotonic)
    monkeypatch.setattr(modes, "Metronome", make_metronome(clock))
    ui = RecordingUi(script, clock)
    modes.stopwatch(ui, ARGS)
    return ui.texts


def test_reset_while_paused_does_not_go_negative(monkeypatch):
    # Run 3s, pause, wait 5s, press reset (still paused), unpause, run 2s, quit.
    texts = run_stopwatch(
        monkeypatch,
        [
            (3.0, INPUT_PAUSE),
            (5.0, INPUT_RESET),
            (0.0, INPUT_PAUSE),
            (2.0, TIME_TICK),
            (0.0, INPUT_EXIT),
        ],
    )

    # Everything drawn after the reset must start at zero and never go negative.
    assert texts[2:] == ["0", "0", "2"], texts


def test_reset_while_running_starts_from_zero(monkeypatch):
    # Run 4s, reset, run 3s, quit.
    texts = run_stopwatch(
        monkeypatch,
        [
            (4.0, INPUT_RESET),
            (3.0, TIME_TICK),
            (0.0, INPUT_EXIT),
        ],
    )

    assert texts == ["0", "0", "3"], texts
