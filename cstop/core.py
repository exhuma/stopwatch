#!/usr/bin/python3
import sys
import termios
import tty
from argparse import ArgumentParser
from collections import namedtuple
from contextlib import contextmanager
from datetime import datetime, timedelta
from itertools import zip_longest
from subprocess import call
from threading import Thread
from time import sleep

TIMERS = {}
GLOBALS = {
    'current_key': None
}

class SimpleTimer:

    def __init__(self, name):
        self.name = name
        self.state_switches = []

    def resume(self):
        if len(self.state_switches) % 2 == 0:
            self.state_switches.append(datetime.now())

    def stop(self):
        if len(self.state_switches) % 2 == 1:
            self.state_switches.append(datetime.now())
    pause = stop

    def start(self):
        pass  # compatibility with thread objects

    def join(self):
        pass  # compatibility with thread objects

    @property
    def seconds(self):
        pairs = zip_longest(self.state_switches[0::2],
                            self.state_switches[1::2])
        total_seconds = 0
        for start, end in pairs:
            real_end = end or datetime.now()
            delta = real_end - start
            total_seconds += delta.total_seconds()
        return int(total_seconds)


@contextmanager
def without_cursor():
    call(['setterm', '-cursor', 'off'])
    yield
    call(['setterm', '-cursor', 'on'])


def getch():
    fd = sys.stdin.fileno()
    old_settings = termios.tcgetattr(fd)
    try:
        tty.setraw(sys.stdin.fileno())
        ch = sys.stdin.read(1)
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
    return ch


def parse_args():
    parser = ArgumentParser()
    parser.add_argument('-s', '--single',
                        help='Only show the currently active timer',
                        action='store_true', default=False)
    return parser.parse_args()


class Timer(Thread):

    def __init__(self, name):
        super().__init__(name=name)
        self.seconds = 0
        self.paused = False
        self.daemon = True
        self.stopped = False

    def run(self):
        while not self.stopped:
            if not self.paused:
                self.seconds += 1
            sleep(1)

    def pause(self):
        self.paused = True

    def resume(self):
        self.paused = False

    def stop(self):
        self.stopped = True


def colorise(key, value):
    if key == GLOBALS['current_key']:
        itemformat = '\033[1;32m%s: %8s\033[0;0m'
    else:
        itemformat = '%s: %8s'
    return itemformat % (key, value)


class Monitor(Thread):

    def __init__(self, single):
        super().__init__()
        self.daemon = True
        self.keep_running = True
        self.single = single

    def run(self):
        while self.keep_running:
            if self.single:
                self.print_single()
            else:
                self.print_multiple()
            sleep(0.1)

    def print_multiple(self):
        data = [(timer.name, timedelta(seconds=timer.seconds))
                for timer in TIMERS.values()]
        items = [colorise(*row) for row in sorted(data)]
        if items:
            print('\r', ' | '.join(items), end='')

    def print_single(self):
        timer = TIMERS.get(GLOBALS['current_key'], None)
        if not timer:
            return
        print('\r',
              colorise(GLOBALS['current_key'],
                       timedelta(seconds=timer.seconds)), end='')

    def stop(self):
        self.keep_running = False


def main():

    args = parse_args()

    print('=== Special Characters ===')
    print('    q: quit')
    print('    p: pause/resume the active counter')
    print('    *: remove (reset) the active counter')
    print('==========================\n')
    print('Press any other button to start a timer with that name')
    print('\nAll keys (except "p" and "q") are case *sensitive*!')
    print('... so you can have a timer "T" and "t"')

    monitor = Monitor(args.single)
    monitor.start()

    last_active = None
    paused = False
    while True:
        char = getch()
        if char.lower() == 'q':
            GLOBALS['current_key'] = None
            break
        if char.lower() == '*':  # Remote the last active timer
            TIMERS.pop(last_active, None)
            last_active = None
            print('\033[2K\r', end='')
            continue
        if char.lower() == 'p':
            if last_active:
                if paused:
                    TIMERS[last_active].resume()
                    paused = False
                    GLOBALS['current_key'] = last_active
                else:
                    for timer in TIMERS.values():
                        timer.pause()
                    paused = True
                    GLOBALS['current_key'] = None
            continue

        last_active = char
        GLOBALS['current_key'] = char

        if char not in TIMERS:
            TIMERS[char] = SimpleTimer(char)
            TIMERS[char].start()

        for k, v in TIMERS.items():
            if k == char:
                v.resume()
            else:
                v.pause()

    for timer in TIMERS.values():
        timer.stop()

    for timer in TIMERS.values():
        timer.join()

    monitor.stop()
    monitor.join()

    if args.single:
        print('\n\n--- Report ------------')
        for name, timer in sorted(TIMERS.items()):
            delta = timedelta(seconds=timer.seconds)
            print('\r', colorise(name, delta))

if __name__ == "__main__":
    with without_cursor():
        main()
