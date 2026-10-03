#!/usr/bin/env bash
# Install WayOfWork.
#   ./install.sh                 the `wow` CLI, symlinked into ~/.local/bin
#   ./install.sh --skills        also the wow-* skills for Claude Code and Codex
#   ./install.sh --bin-dir DIR   the CLI into another directory on PATH
# Skills follow the shared layout: ~/.agents/skills/<skill> points at this repo, and
# ~/.claude/skills/<skill> and ~/.codex/skills/<skill> point at ../../.agents/skills/<skill>.
# Re-running is safe. A real directory with a skill's name is never replaced: the script stops with exit 1.
set -euo pipefail

REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BIN_DIR="$HOME/.local/bin"
SKILLS=0
while [ $# -gt 0 ]; do
  case "$1" in
    --skills) SKILLS=1 ;;
    --bin-dir) BIN_DIR="${2:?--bin-dir needs a directory}"; shift ;;
    -h|--help) sed -n '2,8p' "$0"; exit 0 ;;
    *) echo "unknown argument: $1" >&2; exit 2 ;;
  esac
  shift
done

SOURCE="$REPO/wow/wow"
mkdir -p "$BIN_DIR"
chmod +x "$SOURCE"
ln -sfn "$SOURCE" "$BIN_DIR/wow"
echo "installed: $BIN_DIR/wow -> $SOURCE"
case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) echo "note: $BIN_DIR is not on PATH" ;;
esac

[ "$SKILLS" = 1 ] || exit 0

link() {  # link <target> <path>: create or refresh a symlink, never replace a real file or directory
  if [ -e "$2" ] && [ ! -L "$2" ]; then
    echo "refusing to replace $2: it is not a symlink; move it away and re-run" >&2
    return 1
  fi
  mkdir -p "$(dirname "$2")"
  ln -sfn "$1" "$2"
}

status=0
for dir in "$REPO"/skills/*/; do
  [ -f "$dir/SKILL.md" ] || continue
  name="$(basename "$dir")"
  link "$REPO/skills/$name" "$HOME/.agents/skills/$name" || { status=1; continue; }
  for host in .claude .codex; do
    link "../../.agents/skills/$name" "$HOME/$host/skills/$name" || status=1
  done
  echo "skill: $name (Claude Code, Codex)"
done
exit "$status"
