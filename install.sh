#!/usr/bin/env bash
set -euo pipefail

REPO_URL="${LINUXLOFI_REPO_URL:-https://github.com/JohnDSdev/linuxlofi}"
BRANCH="${LINUXLOFI_BRANCH:-main}"
PREFIX="${LINUXLOFI_PREFIX:-$HOME/.local}"
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

if ! command -v pw-play >/dev/null 2>&1 && ! command -v aplay >/dev/null 2>&1; then
  echo "[linuxlofi] need one audio backend: pw-play (PipeWire) or aplay (ALSA)." >&2
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

install -m 0755 "$SRC_DIR/bin/linuxlofi" "$BIN_DIR/linuxlofi"
install -m 0755 "$SRC_DIR/bin/linuxlofi-music" "$BIN_DIR/linuxlofi-music"
install -m 0755 "$SRC_DIR/bin/linuxlofi-webui" "$BIN_DIR/linuxlofi-webui"

if ! echo "$PATH" | tr ':' '\n' | grep -qx "$BIN_DIR"; then
  echo "[linuxlofi] added binaries to $BIN_DIR"
  echo "[linuxlofi] ensure it's on PATH (restart shell or add: export PATH=\"$BIN_DIR:\$PATH\")"
fi

echo "[linuxlofi] install complete"
echo "[linuxlofi] run: linuxlofi"
echo "[linuxlofi] toggle music daemon: linuxlofi-music"
echo "[linuxlofi] serve web UI: linuxlofi-webui 4173"
