#!/usr/bin/env python3
import argparse
import curses
import json
import math
import os
import random
import signal
import subprocess
import time
from typing import List, Tuple

DEFAULT_REFRESH = 0.12
PROC_REFRESH_SECONDS = 1.0
STATE_FILE = "/tmp/linuxlofi-state.json"
NEXT_TRACK_FILE = "/tmp/linuxlofi-next-track.flag"
APP_HOME = os.environ.get("LINUXLOFI_HOME", os.path.dirname(os.path.abspath(__file__)))
MUSIC_SCRIPT = os.path.join(APP_HOME, "fractal_music.py")

PALETTES = {
    "auto": None,
    "scifi": ("cyan", "blue", "white"),
    "ice": ("white", "cyan", "white"),
    "neon": ("magenta", "cyan", "white"),
    "ocean": ("blue", "cyan", "white"),
    "aurora": ("green", "cyan", "white"),
    "sunset": ("yellow", "magenta", "white"),
    "green": ("green", "yellow", "cyan"),
    "blue": ("blue", "cyan", "white"),
    "amber": ("yellow", "red", "white"),
    "mono": ("white", "white", "white"),
    "pink": ("magenta", "cyan", "white"),
}

COLOR_NAME_TO_CURSES = {
    "black": curses.COLOR_BLACK,
    "red": curses.COLOR_RED,
    "green": curses.COLOR_GREEN,
    "yellow": curses.COLOR_YELLOW,
    "blue": curses.COLOR_BLUE,
    "magenta": curses.COLOR_MAGENTA,
    "cyan": curses.COLOR_CYAN,
    "white": curses.COLOR_WHITE,
}


class CPUReader:
    def __init__(self) -> None:
        self.prev_total = None
        self.prev_idle = None

    def total_usage(self) -> float:
        with open("/proc/stat", "r", encoding="utf-8") as f:
            parts = f.readline().split()[1:]
        vals = [int(x) for x in parts]
        idle = vals[3] + vals[4]
        total = sum(vals)

        if self.prev_total is None:
            self.prev_total = total
            self.prev_idle = idle
            return 0.0

        dt = max(1, total - self.prev_total)
        didle = max(0, idle - self.prev_idle)
        self.prev_total = total
        self.prev_idle = idle
        return max(0.0, min(100.0, 100.0 * (dt - didle) / dt))


class ProcessReader:
    def __init__(self) -> None:
        self.cache: List[Tuple[str, str, str, str, str]] = []
        self.last_fetch = 0.0

    def top_processes(self, limit: int) -> List[Tuple[str, str, str, str, str]]:
        now = time.monotonic()
        if now - self.last_fetch < PROC_REFRESH_SECONDS and self.cache:
            return self.cache[:limit]

        cmd = [
            "ps",
            "-eo",
            "pid,user,pcpu,pmem,comm",
            "--sort=-pcpu",
            "--no-headers",
        ]
        try:
            raw = subprocess.check_output(cmd, text=True, stderr=subprocess.DEVNULL)
        except Exception:
            return self.cache[:limit]

        rows = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            cols = line.split(None, 4)
            if len(cols) != 5:
                continue
            pid, user, cpu, mem, cmd_name = cols
            rows.append((pid, user, cpu, mem, cmd_name))

        self.cache = rows
        self.last_fetch = now
        return rows[:limit]


class MusicStateReader:
    def __init__(self) -> None:
        self.last_good = 0.0
        self.levels = [0.08] * 8
        self.peaks = [0.25] * 8
        self.stats = {"cpu": 0.0, "ram": 0.0, "gpu": 0.0, "vram": 0.0, "tempo": 0.0, "preset": "unknown", "next_in": 0.0}

    def read(self) -> Tuple[List[float], dict, bool]:
        now = time.monotonic()
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            arr = data.get("levels", [])
            if isinstance(arr, list) and len(arr) >= 8:
                for i in range(8):
                    raw = max(0.0, min(1.0, float(arr[i])))
                    self.peaks[i] = max(raw, self.peaks[i] * 0.985, 0.16)
                    target = max(0.0, min(1.0, raw / self.peaks[i]))
                    self.levels[i] += 0.6 * (target - self.levels[i])
                self.stats = {
                    "cpu": float(data.get("cpu", 0.0)),
                    "ram": float(data.get("ram", 0.0)),
                    "gpu": float(data.get("gpu", 0.0)),
                    "vram": float(data.get("vram", 0.0)),
                    "tempo": float(data.get("tempo", 0.0)),
                    "preset": str(data.get("preset", "unknown")),
                    "next_in": float(data.get("next_in", 0.0)),
                }
                self.last_good = now
        except Exception:
            pass

        fresh = (now - self.last_good) <= 2.0
        return list(self.levels), dict(self.stats), fresh


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="htop-like terminal view with lo-fi visualizer bars and real process list"
    )
    parser.add_argument(
        "--palette",
        default="scifi",
        choices=sorted(PALETTES.keys()),
        help="bar color palette",
    )
    parser.add_argument(
        "--bar-color",
        choices=sorted(COLOR_NAME_TO_CURSES.keys()),
        help="override primary bar color",
    )
    parser.add_argument(
        "--peak-color",
        choices=sorted(COLOR_NAME_TO_CURSES.keys()),
        help="override peak cap color",
    )
    parser.add_argument(
        "--text-color",
        choices=sorted(COLOR_NAME_TO_CURSES.keys()),
        help="override table/header color",
    )
    parser.add_argument(
        "--no-music",
        action="store_true",
        help="disable background lo-fi engine startup",
    )
    parser.add_argument("--fps", type=int, default=8, help="refresh rate (4-30)")
    return parser.parse_args()


def detect_dark_bg() -> bool:
    # COLORFGBG usually looks like "15;0" or "default;default;0"
    spec = os.environ.get("COLORFGBG", "")
    chunks = [c for c in spec.replace(";", " ").split() if c.isdigit()]
    if not chunks:
        return True
    try:
        bg = int(chunks[-1])
    except ValueError:
        return True
    return bg <= 7


def choose_palette(args: argparse.Namespace) -> Tuple[str, str, str]:
    if args.bar_color or args.peak_color or args.text_color:
        base = args.bar_color or "green"
        peak = args.peak_color or "yellow"
        text = args.text_color or "white"
        return base, peak, text

    if args.palette != "auto":
        return PALETTES[args.palette]

    if detect_dark_bg():
        return ("cyan", "blue", "white")
    return ("blue", "magenta", "black")


def init_colors(stdscr: curses.window, palette: Tuple[str, str, str]):
    curses.start_color()
    curses.use_default_colors()
    curses.curs_set(0)
    stdscr.nodelay(True)
    stdscr.keypad(True)

    bar_c, peak_c, text_c = palette
    curses.init_pair(1, COLOR_NAME_TO_CURSES[text_c], -1)
    curses.init_pair(2, COLOR_NAME_TO_CURSES[bar_c], -1)
    curses.init_pair(3, COLOR_NAME_TO_CURSES[peak_c], -1)
    curses.init_pair(4, curses.COLOR_WHITE, -1)
    curses.init_pair(5, curses.COLOR_RED, -1)
    curses.init_pair(6, curses.COLOR_YELLOW, -1)
    curses.init_pair(7, curses.COLOR_WHITE, -1)
    curses.init_pair(8, curses.COLOR_CYAN, -1)


def draw_header(stdscr: curses.window, width: int, palette_name: str) -> int:
    logo = [
        "  _ _                  _         __ _ ",
        " | (_)_ __  _   ___  _| | ___   / _(_)",
        " | | | '_ \\| | | \\ \\/ / |/ _ \\ | |_| |",
        " | | | | | | |_| |>  <| | (_) ||  _| |",
        " |_|_|_| |_|\\__,_/_/\\_\\_|\\___(_)_| |_|",
        "                linuxlofi",
    ]
    y = 0
    for line in logo:
        if y >= curses.LINES - 1:
            break
        stdscr.addstr(y, 0, line[: width - 1].ljust(width - 1), curses.color_pair(1) | curses.A_BOLD)
        y += 1

    # Keep space between logo and visualizer with no extra text.
    if y < curses.LINES - 1:
        y += 1
    return y


def generate_spectrum(usage: float, t: float, prev: List[float]) -> List[float]:
    vals = []
    base = usage / 100.0
    for i in range(8):
        phase = t * (1.1 + i * 0.12)
        wave = (math.sin(phase * 2.2 + i * 0.6) + 1.0) * 0.5
        wobble = (math.sin(phase * 0.37 + i * 1.7) + 1.0) * 0.5
        rand = random.random() * 0.25
        target = max(0.05, min(1.0, 0.55 * wave + 0.3 * wobble + 0.5 * base + rand - 0.25))
        smoothed = prev[i] + 0.45 * (target - prev[i])
        vals.append(smoothed)
    return vals


def draw_bars(stdscr: curses.window, top: int, width: int, levels: List[float]) -> int:
    # htop-like horizontal meter rows.
    inner_left = 1
    inner_right = max(inner_left + 12, width - 3)
    inner_width = max(16, inner_right - inner_left - 1)
    meter_width = max(12, min(inner_width - 22, inner_width - 14))
    title = " Visualizer "
    border_top = "+" + "-" * max(1, inner_width) + "+"
    border_bottom = "+" + "-" * max(1, inner_width) + "+"

    if top < curses.LINES - 1:
        stdscr.addstr(top, inner_left - 1, border_top[: width - inner_left], curses.color_pair(1))
        if len(title) < len(border_top) - 2:
            title_x = inner_left + max(0, (len(border_top) - 2 - len(title)) // 2)
            if title_x < width - 1:
                stdscr.addstr(top, title_x, title, curses.color_pair(1) | curses.A_BOLD)
    for idx in range(8):
        y = top + 1 + idx
        if y >= curses.LINES - 1:
            break
        level = max(0.0, min(1.0, levels[idx]))
        fill = int(level * meter_width)
        fill = max(1, fill)
        line_label = f" core{idx + 1:>2} "
        pct = f"{int(level * 100):>3}%"
        meter_full = "#" * fill
        meter_rest = "-" * max(0, meter_width - fill)

        if inner_left - 1 < width - 1:
            stdscr.addstr(y, inner_left - 1, "|", curses.color_pair(1))
        x0 = inner_left
        if x0 + len(line_label) < width - 1:
            stdscr.addstr(y, x0, line_label, curses.color_pair(1))
        x0 += len(line_label)
        if x0 < width - 2:
            stdscr.addstr(y, x0, "[", curses.color_pair(1))
        if x0 + 1 < width - 2:
            stdscr.addstr(y, x0 + 1, meter_full, curses.color_pair(2))
        if x0 + 1 + len(meter_full) < width - 2:
            stdscr.addstr(y, x0 + 1 + len(meter_full), meter_rest, curses.color_pair(4))
        right = x0 + 1 + meter_width
        if right < width - 2:
            stdscr.addstr(y, right, "]", curses.color_pair(1))
        if right + 2 < width - 2:
            stdscr.addstr(y, right + 2, pct, curses.color_pair(3) | curses.A_BOLD)
        if inner_right < width - 1:
            stdscr.addstr(y, inner_right, "|", curses.color_pair(1))
    bottom_y = top + 9
    if bottom_y < curses.LINES - 1:
        stdscr.addstr(bottom_y, inner_left - 1, border_bottom[: width - inner_left], curses.color_pair(1))
    return 10


def draw_process_table(stdscr: curses.window, top: int, width: int, rows: List[Tuple[str, str, str, str, str]]):
    if top >= curses.LINES - 2:
        return
    stdscr.addstr(top, 0, " Processes (real) ".ljust(width - 1), curses.color_pair(1) | curses.A_BOLD)
    header = " PID      USER         CPU%   MEM%   COMMAND"
    stdscr.addstr(top + 1, 0, header[: width - 1].ljust(width - 1), curses.color_pair(1))

    y = top + 2
    for pid, user, cpu, mem, cmd_name in rows:
        if y >= curses.LINES - 1:
            break
        line = f" {pid:<8} {user[:12]:<12} {cpu:>5}  {mem:>6}  {cmd_name}"
        try:
            cpu_f = float(cpu)
        except ValueError:
            cpu_f = 0.0
        if cpu_f >= 20.0:
            row_color = curses.color_pair(5) | curses.A_BOLD
        elif cpu_f >= 10.0:
            row_color = curses.color_pair(6) | curses.A_BOLD
        elif cpu_f >= 3.0:
            row_color = curses.color_pair(7)
        else:
            row_color = curses.color_pair(8)
        stdscr.addstr(y, 0, line[: width - 1].ljust(width - 1), row_color)
        y += 1


def next_palette_name(current: str) -> str:
    names = ["scifi", "ice", "neon", "ocean", "aurora", "sunset", "auto", "green", "blue", "amber", "mono", "pink"]
    idx = names.index(current)
    return names[(idx + 1) % len(names)]


def request_next_track():
    try:
        with open(NEXT_TRACK_FILE, "w", encoding="utf-8") as f:
            f.write(str(time.time()))
    except Exception:
        pass


def is_lofi_running(script_path: str) -> bool:
    try:
        out = subprocess.check_output(["pgrep", "-af", script_path], text=True, stderr=subprocess.DEVNULL)
        for line in out.splitlines():
            if script_path in line and "linuxlofi" not in line and "pgrep -af" not in line:
                return True
    except Exception:
        return False
    return False


def maybe_start_lofi(args: argparse.Namespace) -> Tuple[subprocess.Popen | None, str]:
    if args.no_music:
        return None, "off"
    script = MUSIC_SCRIPT
    if not os.path.exists(script):
        return None, "missing"
    if is_lofi_running(script):
        return None, "external"
    try:
        proc = subprocess.Popen([script], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return proc, "started"
    except Exception:
        return None, "error"


def run(stdscr: curses.window, args: argparse.Namespace):
    palette_name = args.palette
    palette = choose_palette(args)
    init_colors(stdscr, palette)

    cpu_reader = CPUReader()
    proc_reader = ProcessReader()
    music_reader = MusicStateReader()
    levels = [0.1] * 8
    refresh = 1.0 / max(4, min(30, args.fps))
    music_proc, music_mode = maybe_start_lofi(args)

    running = True

    def stop_handler(_sig, _frm):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)

    try:
        while running:
            h, w = stdscr.getmaxyx()
            stdscr.erase()

            usage = cpu_reader.total_usage()
            t = time.monotonic()
            file_levels, music_stats, synced = music_reader.read()
            if synced:
                levels = file_levels
            else:
                levels = generate_spectrum(usage, t, levels)

            header_used = draw_header(stdscr, w, palette_name)

            vis_top = header_used
            vis_used = draw_bars(stdscr, vis_top, w, levels)

            proc_top = vis_top + vis_used + 1
            max_rows = max(3, h - proc_top - 2)
            rows = proc_reader.top_processes(max_rows)
            draw_process_table(stdscr, proc_top, w, rows)

            if synced:
                footer = (
                    f" cpu={music_stats['cpu']:4.1f}% ram={music_stats['ram']:4.1f}% "
                    f"gpu={music_stats['gpu']:4.1f}% vram={music_stats['vram']:4.1f}% "
                    f"bpm={music_stats['tempo']:5.1f}  preset={music_stats['preset'][:16]} "
                    f"next={int(max(0.0, music_stats['next_in'])):>3}s  music={music_mode}/synced  "
                    f"colors: --palette {palette_name} or --bar-color/--peak-color/--text-color "
                )
            else:
                footer = (
                    f" load={usage:5.1f}%  fps={int(1/refresh)}  music={music_mode}/unsynced  "
                    f"colors: --palette {palette_name} or --bar-color/--peak-color/--text-color "
                )
            if len(footer) >= w:
                footer = footer[: w - 1]
            stdscr.addstr(h - 1, 0, footer.ljust(w - 1), curses.color_pair(1))

            stdscr.refresh()

            key = stdscr.getch()
            if key in (ord("q"), ord("Q")):
                break
            if key in (ord("t"), ord("T")):
                request_next_track()
            if key in (ord("c"), ord("C")) and not (args.bar_color or args.peak_color or args.text_color):
                palette_name = next_palette_name(palette_name)
                args.palette = palette_name
                palette = choose_palette(args)
                init_colors(stdscr, palette)

            time.sleep(refresh)
    finally:
        if music_proc is not None and music_proc.poll() is None:
            try:
                music_proc.terminate()
            except Exception:
                pass


def main():
    args = parse_args()
    curses.wrapper(run, args)


if __name__ == "__main__":
    main()
