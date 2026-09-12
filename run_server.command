#!/bin/zsh
set -euo pipefail
cd -- "${0:A:h}"
PROJECT_DIR="$PWD"
PORT=3002

# Restart only a movie-browser process whose working directory is this project.
# This protects unrelated applications that may happen to use port 3002.
LISTENERS="$(lsof -tiTCP:${PORT} -sTCP:LISTEN 2>/dev/null || true)"
if [[ -n "$LISTENERS" ]]; then
  typeset -a MOVIE_PIDS=()
  while IFS= read -r pid; do
    [[ -z "$pid" ]] && continue
    process_command="$(ps -o command= -p "$pid" 2>/dev/null || true)"
    process_cwd="$(lsof -a -p "$pid" -d cwd -Fn 2>/dev/null | sed -n 's/^n//p' || true)"
    if [[ "$process_cwd" == "$PROJECT_DIR" && "$process_command" == *"app/launch.py"* ]]; then
      MOVIE_PIDS+=("$pid")
    else
      echo "Port ${PORT} is being used by another application. It was not stopped."
      exit 1
    fi
  done <<< "$LISTENERS"
  for pid in "${MOVIE_PIDS[@]}"; do
    echo "Stopping the existing movie browser on port ${PORT} (PID ${pid})..."
    kill "$pid"
  done
  for attempt in {1..40}; do
    [[ -z "$(lsof -tiTCP:${PORT} -sTCP:LISTEN 2>/dev/null || true)" ]] && break
    sleep 0.25
  done
  if [[ -n "$(lsof -tiTCP:${PORT} -sTCP:LISTEN 2>/dev/null || true)" ]]; then
    echo "The existing movie browser did not release port ${PORT}."
    exit 1
  fi
fi
exec /usr/bin/python3 app/launch.py "$@"
