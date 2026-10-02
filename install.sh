#!/usr/bin/env bash
# Install the `wow` CLI by symlinking it into a directory on PATH.
set -euo pipefail
TARGET_DIR="${1:-$HOME/.local/bin}"
SOURCE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/wow/wow"
mkdir -p "$TARGET_DIR"
chmod +x "$SOURCE"
ln -sf "$SOURCE" "$TARGET_DIR/wow"
echo "installed: $TARGET_DIR/wow -> $SOURCE"
case ":$PATH:" in
  *":$TARGET_DIR:"*) ;;
  *) echo "note: $TARGET_DIR is not on PATH" ;;
esac
