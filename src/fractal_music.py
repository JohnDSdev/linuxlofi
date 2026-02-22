#!/usr/bin/env python3
import json
import math
import os
import platform
import random
import signal
import shutil
import struct
import subprocess
import time

SR = 44100
STATE_FILE = "/tmp/linuxlofi-state.json"
NEXT_TRACK_FILE = "/tmp/linuxlofi-next-track.flag"
ROTATE_SECONDS = 300
IS_LINUX = platform.system().lower() == "linux"
IS_DARWIN = platform.system().lower() == "darwin"
IS_TERMUX = bool(os.environ.get("TERMUX_VERSION")) or "com.termux" in os.environ.get("PREFIX", "")

PRESETS = [
    {
        "name": "Night Tape",
        "base_tempo": 72,
        "root_midi": 50,
        "scale": [0, 2, 3, 5, 7, 8, 10],
        "progression": [0, 5, 3, 4, 0, 6, 5, 0],
        "motif": [0, None, 7, None, 3, None, 5, None, 7, None, 10, None, 7, 5, 3, None],
        "kick": [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
        "snare": [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
        "hat": [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1],
    },
    {
        "name": "Rain Window",
        "base_tempo": 68,
        "root_midi": 53,
        "scale": [0, 2, 3, 5, 7, 8, 10],
        "progression": [0, 3, 5, 4, 0, 5, 3, 0],
        "motif": [0, None, 3, None, 5, None, 7, None, 5, None, 3, None, 2, None, 0, None],
        "kick": [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
        "snare": [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
        "hat": [0, 1, 0, 1, 0, 1, 1, 0, 0, 1, 0, 1, 0, 1, 0, 1],
    },
    {
        "name": "Dusk Walk",
        "base_tempo": 76,
        "root_midi": 57,
        "scale": [0, 2, 3, 5, 7, 9, 10],
        "progression": [0, 4, 5, 3, 0, 2, 5, 0],
        "motif": [0, None, 7, None, 9, None, 5, None, 3, None, 2, None, 5, 7, 9, None],
        "kick": [1, 0, 0, 1, 1, 0, 0, 0, 1, 0, 0, 1, 1, 0, 0, 0],
        "snare": [0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0],
        "hat": [0, 1, 1, 1, 0, 1, 0, 1, 0, 1, 1, 1, 0, 1, 0, 1],
    },
    {
        "name": "Cozy Corner",
        "base_tempo": 64,
        "root_midi": 48,
        "scale": [0, 3, 5, 7, 10],
        "progression": [0, 2, 3, 2, 0, 3, 2, 0],
        "motif": [0, None, 5, None, 7, None, 10, None, 7, None, 5, None, 3, None, 0, None],
        "kick": [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
        "snare": [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
        "hat": [0, 1, 0, 1, 0, 0, 1, 0, 0, 1, 0, 1, 0, 0, 1, 0],
    },
    {
        "name": "Dusty Grooves",
        "base_tempo": 82,
        "root_midi": 55,
        "scale": [0, 2, 3, 5, 7, 8, 10],
        "progression": [0, 5, 6, 4, 0, 5, 3, 0],
        "motif": [0, None, 7, 5, 3, None, 5, None, 7, None, 10, 7, 5, None, 3, None],
        "kick": [1, 0, 1, 0, 1, 0, 0, 0, 1, 0, 1, 0, 1, 0, 0, 0],
        "snare": [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 1, 0],
        "hat": [0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 0, 1],
    },
    {
        "name": "Subway Lights",
        "base_tempo": 88,
        "root_midi": 52,
        "scale": [0, 2, 3, 5, 7, 8, 10],
        "progression": [0, 4, 5, 3, 0, 2, 4, 0],
        "motif": [0, 3, None, 7, None, 5, None, 10, 7, None, 5, None, 3, None, 2, None],
        "kick": [1, 0, 0, 1, 1, 0, 0, 1, 1, 0, 0, 0, 1, 0, 0, 0],
        "snare": [0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 0],
        "hat": [0, 1, 1, 0, 0, 1, 1, 1, 0, 1, 1, 0, 0, 1, 1, 1],
    },
    {
        "name": "Cafe Late",
        "base_tempo": 74,
        "root_midi": 59,
        "scale": [0, 2, 3, 5, 7, 9, 10],
        "progression": [0, 4, 2, 5, 0, 3, 4, 0],
        "motif": [0, None, 3, None, 5, None, 7, None, 9, None, 7, None, 5, 3, 2, None],
        "kick": [1, 0, 0, 0, 1, 0, 1, 0, 1, 0, 0, 0, 1, 0, 0, 0],
        "snare": [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
        "hat": [0, 1, 0, 1, 1, 0, 1, 0, 0, 1, 0, 1, 1, 0, 1, 0],
    },
    {
        "name": "Moon Study",
        "base_tempo": 60,
        "root_midi": 54,
        "scale": [0, 3, 5, 7, 10],
        "progression": [0, 2, 3, 2, 0, 2, 3, 0],
        "motif": [0, None, 5, None, 7, None, 10, None, 7, None, 5, None, 3, None, 0, None],
        "kick": [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
        "snare": [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
        "hat": [0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0],
    },
    {
        "name": "Neon Drift",
        "base_tempo": 96,
        "root_midi": 49,
        "scale": [0, 2, 3, 5, 7, 8, 10],
        "progression": [0, 5, 3, 4, 0, 6, 5, 0],
        "motif": [0, None, 7, None, 3, None, 5, None, 7, None, 10, None, 7, 5, 3, None],
        "kick": [1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0, 1, 0, 0, 0],
        "snare": [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0, 1, 0, 0, 0],
        "hat": [0, 1, 0, 1, 0, 1, 1, 1, 0, 1, 0, 1, 1, 1, 0, 1],
    },
    {
        "name": "Morning Transit",
        "base_tempo": 108,
        "root_midi": 56,
        "scale": [0, 2, 3, 5, 7, 9, 10],
        "progression": [0, 4, 5, 6, 0, 2, 4, 0],
        "motif": [0, 2, None, 5, 7, None, 9, None, 10, None, 7, None, 5, 3, None, 2],
        "kick": [1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 0, 1, 1, 0, 0, 0],
        "snare": [0, 0, 0, 0, 1, 0, 1, 0, 0, 0, 0, 0, 1, 0, 1, 0],
        "hat": [0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1, 0, 1, 1, 1],
    },
]


def get_player_candidates():
    forced = os.environ.get("LINUXLOFI_AUDIO_BACKEND", "").strip().lower()
    base = [
        ("pw-play", ["pw-play", "--rate", str(SR), "--channels", "1", "--format", "s16", "-"]),
        ("aplay", ["aplay", "-q", "-f", "S16_LE", "-r", str(SR), "-c", "1"]),
        (
            "mpv",
            [
                "mpv",
                "--no-video",
                "--really-quiet",
                "--audio-display=no",
                "--demuxer=rawaudio",
                "--demuxer-rawaudio-format=s16le",
                f"--demuxer-rawaudio-rate={SR}",
                "--demuxer-rawaudio-channels=1",
                "-",
            ],
        ),
        ("ffplay", ["ffplay", "-v", "error", "-nostats", "-nodisp", "-f", "s16le", "-ar", str(SR), "-ac", "1", "-i", "-"]),
    ]

    # Termux tends to work best with mpv; prefer it there.
    if IS_TERMUX:
        preferred = ["mpv", "ffplay", "pw-play", "aplay"]
    else:
        preferred = ["pw-play", "aplay", "mpv", "ffplay"]

    ordered = []
    for name in preferred:
        for n, cmd in base:
            if n == name:
                ordered.append((n, cmd))
                break

    if forced:
        ordered = [(n, cmd) for n, cmd in ordered if n == forced]
    return ordered


def start_player():
    for name, cmd in get_player_candidates():
        if not shutil.which(cmd[0]):
            continue
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if proc.stdin is None:
                continue
            proc.stdin.write(b"\x00" * 4096)
            proc.stdin.flush()
            return proc, name
        except Exception:
            try:
                proc.terminate()
            except Exception:
                pass
            continue
    forced = os.environ.get("LINUXLOFI_AUDIO_BACKEND", "").strip().lower()
    if forced:
        raise RuntimeError(f"Forced backend '{forced}' is unavailable or failed to start")
    raise RuntimeError("No working audio backend found (tried pw-play, aplay, mpv, ffplay)")


def read_cpu_pair():
    if not IS_LINUX or not os.path.exists("/proc/stat"):
        return None
    with open("/proc/stat", "r", encoding="utf-8") as f:
        p = f.readline().split()[1:]
    vals = [int(x) for x in p]
    idle = vals[3] + vals[4]
    total = sum(vals)
    return total, idle


def read_cpu_pct_fallback():
    cores = max(1, os.cpu_count() or 1)
    try:
        out = subprocess.check_output(["ps", "-A", "-o", "%cpu"], text=True, stderr=subprocess.DEVNULL)
        vals = [float(x.strip()) for x in out.splitlines()[1:] if x.strip()]
        return clamp(sum(vals) / cores, 0.0, 100.0)
    except Exception:
        pass
    try:
        load = os.getloadavg()[0]
        return clamp((load / cores) * 100.0, 0.0, 100.0)
    except Exception:
        return 0.0


def read_ram_pct():
    if IS_LINUX and os.path.exists("/proc/meminfo"):
        total = 1
        avail = 0
        with open("/proc/meminfo", "r", encoding="utf-8") as f:
            for line in f:
                if line.startswith("MemTotal:"):
                    total = int(line.split()[1])
                elif line.startswith("MemAvailable:"):
                    avail = int(line.split()[1])
        return 100.0 * max(0, total - avail) / max(1, total)

    if IS_DARWIN:
        try:
            total_b = int(
                subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True, stderr=subprocess.DEVNULL).strip()
            )
            vm = subprocess.check_output(["vm_stat"], text=True, stderr=subprocess.DEVNULL)
            page_size = 4096
            for line in vm.splitlines():
                if "page size of" in line:
                    chunk = line.split("page size of", 1)[1]
                    digits = "".join(ch for ch in chunk if ch.isdigit())
                    if digits:
                        page_size = int(digits)
                    break

            pages = {}
            for line in vm.splitlines():
                if ":" not in line:
                    continue
                k, v = line.split(":", 1)
                num = "".join(ch for ch in v if ch.isdigit())
                if not num:
                    continue
                pages[k.strip()] = int(num)

            free_like = (
                pages.get("Pages free", 0)
                + pages.get("Pages inactive", 0)
                + pages.get("Pages speculative", 0)
            )
            avail_b = free_like * page_size
            used_b = max(0, total_b - avail_b)
            return 100.0 * used_b / max(1, total_b)
        except Exception:
            pass

    total = 1
    avail = 0
    return 100.0 * max(0, total - avail) / max(1, total)


def read_gpu_metrics(last_ok):
    try:
        out = subprocess.check_output(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader,nounits",
            ],
            stderr=subprocess.DEVNULL,
            timeout=0.35,
            text=True,
        ).strip()
        if not out:
            return last_ok
        gpu_s, used_s, total_s = [x.strip() for x in out.split(",")[:3]]
        gpu = float(gpu_s)
        vram = 100.0 * float(used_s) / max(1.0, float(total_s))
        return gpu, vram
    except Exception:
        return last_ok


def midi_to_hz(midi):
    return 440.0 * (2.0 ** ((midi - 69.0) / 12.0))


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def softclip(x):
    return math.tanh(x)


def write_state(payload):
    tmp = f"{STATE_FILE}.tmp"
    try:
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        os.replace(tmp, STATE_FILE)
    except Exception:
        pass


def consume_next_track_flag():
    if not os.path.exists(NEXT_TRACK_FILE):
        return False
    try:
        os.remove(NEXT_TRACK_FILE)
    except OSError:
        pass
    return True


def main():
    player, backend_name = start_player()
    if player.stdin is None:
        return

    running = True

    def stop_handler(_sig, _frm):
        nonlocal running
        running = False

    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)

    cpu_pair = read_cpu_pair()
    last_gpu = (0.0, 0.0)
    last_gpu_poll = 0.0

    current_idx = 8  # Neon Drift default
    last_change = time.monotonic()
    pending_track_change = False
    live_tempo = float(PRESETS[current_idx]["base_tempo"])
    smooth_load = 0.0

    step = 0
    ph_bass = 0.0
    ph_sub = 0.0
    ph_pad = [0.0, 0.0, 0.0]
    ph_key = 0.0

    while running:
        now = time.monotonic()

        if consume_next_track_flag() or (now - last_change >= ROTATE_SECONDS):
            pending_track_change = True
        if pending_track_change and step % 16 == 0:
            current_idx = (current_idx + 1) % len(PRESETS)
            last_change = now
            pending_track_change = False

        preset = PRESETS[current_idx]
        base_tempo = float(preset["base_tempo"])
        scale = preset["scale"]
        progression = preset["progression"]
        motif = preset["motif"]
        kick_pat = preset["kick"]
        snare_pat = preset["snare"]
        hat_pat = preset["hat"]
        root_midi = int(preset["root_midi"])

        if cpu_pair is not None:
            cpu_t0, cpu_i0 = cpu_pair
            next_pair = read_cpu_pair()
            if next_pair is not None:
                cpu_t1, cpu_i1 = next_pair
                dt = max(1, cpu_t1 - cpu_t0)
                cpu_pct = 100.0 * max(0, dt - (cpu_i1 - cpu_i0)) / dt
                cpu_pair = next_pair
            else:
                cpu_pct = read_cpu_pct_fallback()
                cpu_pair = None
        else:
            cpu_pct = read_cpu_pct_fallback()

        ram_pct = read_ram_pct()

        if now - last_gpu_poll > 1.2:
            last_gpu = read_gpu_metrics(last_gpu)
            last_gpu_poll = now
        gpu_pct, vram_pct = last_gpu

        weighted = cpu_pct * 0.34 + ram_pct * 0.20 + gpu_pct * 0.27 + vram_pct * 0.19
        load = clamp(weighted / 100.0, 0.0, 1.0)
        peak = max(cpu_pct, gpu_pct)
        rush = clamp((peak - 85.0) / 15.0, 0.0, 1.0)

        smooth_load += 0.14 * (load - smooth_load)
        target_tempo = base_tempo + (smooth_load * 22.0) + (rush * 12.0) - 6.0
        live_tempo += 0.12 * (target_tempo - live_tempo)
        live_tempo = clamp(live_tempo, 58.0, 128.0)

        step_sec = 60.0 / live_tempo / 4.0
        n = max(256, int(SR * step_sec))

        bar = step // 16
        step16 = step % 16

        cpu_drive = clamp(cpu_pct / 100.0, 0.0, 1.0)
        ram_warmth = clamp(ram_pct / 100.0, 0.0, 1.0)
        gpu_motion = clamp(gpu_pct / 100.0, 0.0, 1.0)
        vram_spark = clamp(vram_pct / 100.0, 0.0, 1.0)

        degree = progression[bar % len(progression)]
        chord_root = root_midi + scale[degree % len(scale)]
        chord = [chord_root, chord_root + 3, chord_root + 7]

        bass_note = chord_root - 12
        if step16 in (8, 9) and random.random() < 0.35:
            bass_note += 7

        motif_note = motif[step16]
        key_note = None if motif_note is None else chord_root + motif_note
        if key_note is not None and gpu_motion > 0.65 and random.random() < (gpu_motion - 0.55) * 0.25:
            key_note += 12

        kick_hit = kick_pat[step16] == 1
        snare_hit = snare_pat[step16] == 1
        hat_hit = hat_pat[step16] == 1

        bass_gain = 0.12 + 0.14 * cpu_drive
        sub_gain = 0.08 + 0.12 * cpu_drive
        pad_gain = 0.05 + 0.12 * ram_warmth
        key_gain = 0.07 + 0.15 * gpu_motion
        kick_amp = (0.72 + 0.33 * cpu_drive) if kick_hit else 0.0
        snare_amp = (0.20 + 0.22 * vram_spark) if snare_hit else 0.0
        hat_amp = (0.10 + 0.30 * vram_spark) if hat_hit else 0.0

        bass_hz = midi_to_hz(bass_note)
        sub_hz = bass_hz * 0.5
        key_hz = midi_to_hz(key_note) if key_note is not None else 0.0
        pad_hz = [midi_to_hz(chord[0]), midi_to_hz(chord[1]), midi_to_hz(chord[2])]

        buf = bytearray()

        for i in range(n):
            g = i / n

            ph_bass += (2.0 * math.pi * bass_hz) / SR
            ph_sub += (2.0 * math.pi * sub_hz) / SR
            bass_env = (1.0 - g) ** 1.08
            bass = math.sin(ph_bass) * bass_gain * bass_env
            sub = math.sin(ph_sub) * sub_gain * bass_env

            pad = 0.0
            pad_env = (1.0 - g) ** (0.28 + 0.35 * (1.0 - ram_warmth))
            for j in range(3):
                ph_pad[j] += (2.0 * math.pi * pad_hz[j]) / SR
                pad += math.sin(ph_pad[j])
            pad = (pad / 3.0) * pad_gain * pad_env

            key = 0.0
            if key_note is not None:
                ph_key += (2.0 * math.pi * key_hz) / SR
                key_env = (1.0 - g) ** 1.9
                key = (math.sin(ph_key) + 0.45 * math.sin(ph_key * 2.0)) * key_gain * key_env

            kick = 0.0
            if kick_hit:
                k_env = math.exp(-13.0 * g)
                kf = 145.0 - 95.0 * g
                kick = math.sin(2.0 * math.pi * kf * (i / SR)) * kick_amp * k_env

            snare = 0.0
            if snare_hit:
                s_env = math.exp(-22.0 * g)
                s1 = math.sin(2.0 * math.pi * 180.0 * (i / SR))
                s2 = math.sin(2.0 * math.pi * 330.0 * (i / SR))
                snare = (0.7 * s1 + 0.3 * s2) * snare_amp * s_env

            hat = 0.0
            if hat_hit:
                h_env = math.exp(-56.0 * g)
                h1 = math.sin(2.0 * math.pi * 5200.0 * (i / SR))
                h2 = math.sin(2.0 * math.pi * 7200.0 * (i / SR))
                hat = (0.65 * h1 + 0.35 * h2) * hat_amp * h_env

            mix = bass + sub + pad + key + kick + snare + hat
            mix = softclip(mix * 1.35) * 0.72
            sample = int(clamp(mix, -1.0, 1.0) * 32767)
            buf += struct.pack("<h", sample)

        vis_levels = [
            clamp(kick_amp, 0.0, 1.0),
            clamp(bass_gain * 1.8, 0.0, 1.0),
            clamp(sub_gain * 1.8, 0.0, 1.0),
            clamp(pad_gain * 1.8, 0.0, 1.0),
            clamp(key_gain * 1.8, 0.0, 1.0),
            clamp(snare_amp * 2.2, 0.0, 1.0),
            clamp(hat_amp * 2.2, 0.0, 1.0),
            clamp((kick_amp + bass_gain + pad_gain + key_gain + snare_amp + hat_amp) / 2.4, 0.0, 1.0),
        ]
        write_state(
            {
                "ts": now,
                "tempo": live_tempo,
                "cpu": cpu_pct,
                "ram": ram_pct,
                "gpu": gpu_pct,
                "vram": vram_pct,
                "preset": preset["name"],
                "preset_index": current_idx,
                "audio_backend": backend_name,
                "next_in": max(0.0, ROTATE_SECONDS - (now - last_change)),
                "levels": vis_levels,
                "components": {
                    "cpu_drive": cpu_drive,
                    "ram_warmth": ram_warmth,
                    "gpu_motion": gpu_motion,
                    "vram_spark": vram_spark,
                },
            }
        )

        step += 1

        try:
            player.stdin.write(buf)
            player.stdin.flush()
        except (BrokenPipeError, OSError):
            break

    try:
        player.stdin.close()
    except Exception:
        pass
    try:
        player.terminate()
    except Exception:
        pass


if __name__ == "__main__":
    main()
