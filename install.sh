#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${LINUXLOFI_REPO_URL:-https://github.com/JohnDSdev/linuxlofi}"
BRANCH="${LINUXLOFI_BRANCH:-main}"
DEFAULT_PREFIX="$HOME/.local"
if [ -n "${PREFIX:-}" ] && [ -d "${PREFIX:-}" ]; then
  case "$PREFIX" in
    */com.termux/files/usr) DEFAULT_PREFIX="$PREFIX" ;;
  esac
fi
if [ -n "${TERMUX_VERSION:-}" ] && [ -n "${PREFIX:-}" ] && [ -d "${PREFIX:-}" ]; then
  DEFAULT_PREFIX="$PREFIX"
fi
PREFIX="${LINUXLOFI_PREFIX:-$DEFAULT_PREFIX}"
BIN_DIR="$PREFIX/bin"
APP_DIR="$PREFIX/share/linuxlofi"
TMP_DIR="$(mktemp -d)"
cleanup() { rm -rf "$TMP_DIR"; }
trap cleanup EXIT

need_cmd() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "[linuxlofi] missing dependency: $1" >&2
    exit 1
  }
}

need_cmd bash
need_cmd python3
need_cmd tar
need_cmd curl

if ! command -v pw-play >/dev/null 2>&1 \
  && ! command -v aplay >/dev/null 2>&1 \
  && ! command -v ffplay >/dev/null 2>&1 \
  && ! command -v mpv >/dev/null 2>&1; then
  echo "[linuxlofi] no supported audio backend found." >&2
  echo "[linuxlofi] install one of: pw-play, aplay, ffplay, mpv" >&2
  if [ -n "${TERMUX_VERSION:-}" ] || [ -n "${PREFIX:-}" ] && [ "${PREFIX#*com.termux}" != "$PREFIX" ]; then
    echo "[linuxlofi] Termux tip: pkg install mpv" >&2
  else
    echo "[linuxlofi] Linux/macOS tip: install ffmpeg (ffplay) or mpv" >&2
  fi
  exit 1
fi

ARCHIVE_URL="$REPO_URL/archive/refs/heads/$BRANCH.tar.gz"
echo "[linuxlofi] downloading $ARCHIVE_URL"
curl -fsSL "$ARCHIVE_URL" -o "$TMP_DIR/linuxlofi.tar.gz"
tar -xzf "$TMP_DIR/linuxlofi.tar.gz" -C "$TMP_DIR"
SRC_DIR="$(find "$TMP_DIR" -maxdepth 1 -type d -name 'linuxlofi-*' | head -n1)"

if [ -z "$SRC_DIR" ] || [ ! -d "$SRC_DIR" ]; then
  echo "[linuxlofi] failed to unpack source archive" >&2
  exit 1
fi

mkdir -p "$BIN_DIR" "$APP_DIR"
rm -rf "$APP_DIR/src" "$APP_DIR/webui" "$APP_DIR/demo"
cp -r "$SRC_DIR/src" "$APP_DIR/src"
cp -r "$SRC_DIR/webui" "$APP_DIR/webui"
cp -r "$SRC_DIR/demo" "$APP_DIR/demo"

cat > "$BIN_DIR/linuxlofi" <<EOF
#!/usr/bin/env bash
set -euo pipefail
APP_DIR="\${LINUXLOFI_HOME:-$APP_DIR}"
SELF_DIR="\$(CDPATH= cd -- "\$(dirname -- "\$0")" && pwd)"
ALT_DIR="\$(CDPATH= cd -- "\$SELF_DIR/../share/linuxlofi" 2>/dev/null && pwd || true)"
if [ ! -f "\$APP_DIR/src/linuxlofi.py" ] && [ -n "\$ALT_DIR" ] && [ -f "\$ALT_DIR/src/linuxlofi.py" ]; then
  APP_DIR="\$ALT_DIR"
fi
if [ ! -f "\$APP_DIR/src/linuxlofi.py" ]; then
  echo "[linuxlofi] missing app files at: \$APP_DIR/src/linuxlofi.py" >&2
  echo "[linuxlofi] reinstall with: curl -fsSL https://raw.githubusercontent.com/JohnDSdev/linuxlofi/main/install.sh | bash" >&2
  exit 1
fi
PYTHON_BIN="\$(command -v python3 || command -v python || true)"
if [ -z "\$PYTHON_BIN" ]; then
  echo "[linuxlofi] python3/python not found" >&2
  exit 1
fi
exec "\$PYTHON_BIN" "\$APP_DIR/src/linuxlofi.py" "\$@"
EOF

cat > "$BIN_DIR/linuxlofi-music" <<EOF
#!/usr/bin/env bash
set -euo pipefail
RUNTIME_DIR="\${XDG_RUNTIME_DIR:-/tmp}"
if [ ! -w "\$RUNTIME_DIR" ]; then
  RUNTIME_DIR="/tmp"
fi
PIDFILE="\$RUNTIME_DIR/fractal-music.pid"
APP_DIR="\${LINUXLOFI_HOME:-$APP_DIR}"
SELF_DIR="\$(CDPATH= cd -- "\$(dirname -- "\$0")" && pwd)"
ALT_DIR="\$(CDPATH= cd -- "\$SELF_DIR/../share/linuxlofi" 2>/dev/null && pwd || true)"
if [ ! -f "\$APP_DIR/src/fractal_music.py" ] && [ -n "\$ALT_DIR" ] && [ -f "\$ALT_DIR/src/fractal_music.py" ]; then
  APP_DIR="\$ALT_DIR"
fi
SCRIPT="\$APP_DIR/src/fractal_music.py"
PYTHON_BIN="\$(command -v python3 || command -v python || true)"
if [ -z "\$PYTHON_BIN" ]; then
  echo "[linuxlofi] python3/python not found" >&2
  exit 1
fi

if [ -f "\$PIDFILE" ]; then
  PID="\$(cat "\$PIDFILE" 2>/dev/null || true)"
  if [ -n "\$PID" ] && kill -0 "\$PID" 2>/dev/null; then
    kill "\$PID" 2>/dev/null || true
    rm -f "\$PIDFILE"
    command -v notify-send >/dev/null 2>&1 && notify-send "linuxlofi" "music stopped"
    exit 0
  fi
fi

nohup "\$PYTHON_BIN" "\$SCRIPT" >/tmp/fractal-music.log 2>&1 &
echo "\$!" > "\$PIDFILE"
command -v notify-send >/dev/null 2>&1 && notify-send "linuxlofi" "music started"
EOF

cat > "$BIN_DIR/linuxlofi-webui" <<EOF
#!/usr/bin/env bash
set -euo pipefail
PORT="\${1:-4173}"
APP_DIR="\${LINUXLOFI_HOME:-$APP_DIR}"
SELF_DIR="\$(CDPATH= cd -- "\$(dirname -- "\$0")" && pwd)"
ALT_DIR="\$(CDPATH= cd -- "\$SELF_DIR/../share/linuxlofi" 2>/dev/null && pwd || true)"
if [ ! -d "\$APP_DIR/webui" ] && [ -n "\$ALT_DIR" ] && [ -d "\$ALT_DIR/webui" ]; then
  APP_DIR="\$ALT_DIR"
fi
PYTHON_BIN="\$(command -v python3 || command -v python || true)"
if [ -z "\$PYTHON_BIN" ]; then
  echo "[linuxlofi] python3/python not found" >&2
  exit 1
fi
cd "\$APP_DIR/webui"
exec "\$PYTHON_BIN" -m http.server "\$PORT" --bind 127.0.0.1
EOF

chmod +x "$BIN_DIR/linuxlofi" "$BIN_DIR/linuxlofi-music" "$BIN_DIR/linuxlofi-webui"

# Fallback: if BIN_DIR is not on PATH but ~/bin is, mirror commands there.
if ! echo "$PATH" | tr ':' '\n' | grep -qx "$BIN_DIR"; then
  if echo "$PATH" | tr ':' '\n' | grep -qx "$HOME/bin"; then
    mkdir -p "$HOME/bin"
    ln -sf "$BIN_DIR/linuxlofi" "$HOME/bin/linuxlofi"
    ln -sf "$BIN_DIR/linuxlofi-music" "$HOME/bin/linuxlofi-music"
    ln -sf "$BIN_DIR/linuxlofi-webui" "$HOME/bin/linuxlofi-webui"
  fi
fi

if ! echo "$PATH" | tr ':' '\n' | grep -qx "$BIN_DIR"; then
  echo "[linuxlofi] added binaries to $BIN_DIR"
  echo "[linuxlofi] ensure it's on PATH (restart shell or add: export PATH=\"$BIN_DIR:\$PATH\")"
fi

echo "[linuxlofi] install complete"
echo "[linuxlofi] app dir: $APP_DIR"
echo "[linuxlofi] run: linuxlofi"
echo "[linuxlofi] toggle music daemon: linuxlofi-music"
echo "[linuxlofi] serve web UI: linuxlofi-webui 4173"
