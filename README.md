# linuxlofi

`linuxlofi` is a lightweight terminal lo-fi workstation:
- htop-style TUI with 8 horizontal visualizer bars
- real process list from your machine (`ps`-based)
- procedural lo-fi generator (notes + instruments only, no SFX)
- adaptive composition using live CPU/RAM/GPU/VRAM stats
- 10 built-in track presets with auto-rotation every 5 minutes
- `t` key to force an instant preset/track change

## Demo

Inline GIF preview:

![linuxlofi demo](demo/linuxlofi-demo.gif)

Watch full video:
- [`demo/screenrec-20260222-171010.mp4`](demo/screenrec-20260222-171010.mp4)

Listen to demo audio:

<audio controls preload="metadata">
  <source src="https://raw.githubusercontent.com/JohnDSdev/linuxlofi/main/demo/linuxlofi-demo-audio.mp3" type="audio/mpeg">
</audio>

Audio file link:
- [`demo/linuxlofi-demo-audio.mp3`](demo/linuxlofi-demo-audio.mp3)

## One-line installer

```bash
curl -fsSL https://raw.githubusercontent.com/JohnDSdev/linuxlofi/main/install.sh | bash
```

## Requirements

- Linux
- `python3`
- `ps` (available by default on Linux/macOS/Termux)
- audio backend: `pw-play` (PipeWire), `aplay` (ALSA), or `ffplay` (FFmpeg)
- optional GPU metrics: `nvidia-smi` (if NVIDIA is present)

## OS support

- Linux (native): supported.
- macOS (native): supported.
- Termux on Android: supported.
- Windows (native): not supported.
- BSDs (native): not supported.

Support notes:
- Linux: best experience with `pw-play` or `aplay` (or `ffplay`).
- macOS: use `ffplay` (install via FFmpeg).
- Termux: use `ffplay` from the Termux `ffmpeg` package.

## Usage

Start TUI:

```bash
linuxlofi
```

Start TUI without auto-starting music engine:

```bash
linuxlofi --no-music
```

Palette/color examples:

```bash
linuxlofi --palette scifi
linuxlofi --palette auto
linuxlofi --bar-color blue --peak-color white --text-color cyan
```

Toggle standalone music engine (background):

```bash
linuxlofi-music
```

Serve the original web UI on localhost:

```bash
linuxlofi-webui 4173
# open http://127.0.0.1:4173
```

## Controls

- `q`: quit
- `t`: force next track preset
- `c`: cycle palette (when explicit custom colors are not set)

## How it works

- `src/fractal_music.py` synthesizes lo-fi audio in real-time and writes:
  - PCM stream to `pw-play` or `aplay`
  - sync state to `/tmp/linuxlofi-state.json`
- `src/linuxlofi.py` renders the TUI with `curses` and consumes sync state.
- When synced state is present, bars map to musical components:
  - kick energy
  - bass/sub movement
  - pad/key density
  - snare/hat intensity
  - combined master energy
- Adaptive behavior by utilization:
  - CPU -> low-end drive + kick intensity
  - RAM -> pad warmth/density
  - GPU -> melodic movement
  - VRAM -> snare/hat sparkle
- Tempo and arrangement react to weighted utilization and rotate presets every 300s.

## Hyprland integration (optional)

Super+M toggle example:

```ini
bindd = $mainMod, M, toggle linuxlofi music, exec, linuxlofi-music
```

Force track change from terminal:

```bash
touch /tmp/linuxlofi-next-track.flag
```

## Portability notes

This repo runs on Linux, macOS, and Termux with one of these audio backends: `pw-play`, `aplay`, `ffplay`.
If `nvidia-smi` is missing, GPU/VRAM metrics gracefully fall back to zero while audio still runs.
