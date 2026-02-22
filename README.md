# linuxlofi

A lightweight terminal lo-fi workstation — htop-style TUI, real process list, and procedural music that adapts to your CPU/RAM/GPU/VRAM in real-time.

![linuxlofi demo](demo/linuxlofi-demo.gif)

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/JohnDSdev/linuxlofi/main/install.sh | bash
```

**Requires:** `python3` + one of `pw-play`, `aplay`, `ffplay`, or `mpv` · Linux, macOS, or Termux

## Usage

```bash
linuxlofi                   # start TUI + music
linuxlofi --no-music        # TUI only
linuxlofi-music             # toggle background music daemon
linuxlofi-webui 4173        # web UI at http://127.0.0.1:4173
linuxlofi --palette scifi   # color themes: scifi, neon, ocean, aurora, sunset, mono...
```

**Controls:** `q` quit · `t` next track · `c` cycle palette

## Hyprland

```ini
bindd = $mainMod, M, toggle linuxlofi music, exec, linuxlofi-music
```
