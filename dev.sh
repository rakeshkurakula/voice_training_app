#!/usr/bin/env bash
set -euo pipefail

# VoiceCoach 2.0 Dev Manager
# Controls backend (FastAPI) and frontend (Vite) start/stop/status/logs

ROOT_DIR="$(cd "$(dirname "$0")" && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
FRONTEND_DIR="$ROOT_DIR/frontend"
VENV_PATH="$ROOT_DIR/venv/bin/activate"
LOG_DIR="$ROOT_DIR/logs"
RUN_DIR="$ROOT_DIR/.run"

BACKEND_PORT=8000
FRONTEND_PORT=3000

mkdir -p "$LOG_DIR" "$RUN_DIR"

cyan()  { printf "\033[36m%s\033[0m\n" "$*"; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
red()   { printf "\033[31m%s\033[0m\n" "$*"; }
yellow(){ printf "\033[33m%s\033[0m\n" "$*"; }

pid_on_port() { local port=$1; lsof -ti tcp:"$port" 2>/dev/null || true; }
kill_pid() {
  local pid=$1
  if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
    kill -15 "$pid" 2>/dev/null || true
    sleep 1
    kill -9 "$pid" 2>/dev/null || true
  fi
}

start_backend() {
  if pids=$(pid_on_port "$BACKEND_PORT"); [ -n "${pids}" ]; then
    yellow "Backend already running on :$BACKEND_PORT (PID: $pids)"
    return 0
  fi
  cyan "Starting backend (FastAPI) on :$BACKEND_PORT..."
  if [ -f "$VENV_PATH" ]; then
    # shellcheck disable=SC1090
    source "$VENV_PATH"
  fi
  cd "$BACKEND_DIR"
  nohup python main.py >"$LOG_DIR/backend.log" 2>&1 & echo $! >"$RUN_DIR/backend.pid"
  green "Backend started (PID $(cat "$RUN_DIR/backend.pid"))"
}

start_frontend() {
  if pids=$(pid_on_port "$FRONTEND_PORT"); [ -n "${pids}" ]; then
    yellow "Frontend already running on :$FRONTEND_PORT (PID: $pids)"
    return 0
  fi
  cyan "Starting frontend (Vite) on :$FRONTEND_PORT..."
  cd "$FRONTEND_DIR"
  nohup npm run dev >"$LOG_DIR/frontend.log" 2>&1 & echo $! >"$RUN_DIR/frontend.pid"
  green "Frontend started (PID $(cat "$RUN_DIR/frontend.pid"))"
}

stop_backend() {
  cyan "Stopping backend..."
  if [ -f "$RUN_DIR/backend.pid" ]; then
    kill_pid "$(cat "$RUN_DIR/backend.pid" || true)" || true
    rm -f "$RUN_DIR/backend.pid"
  fi
  if pids=$(pid_on_port "$BACKEND_PORT"); [ -n "${pids}" ]; then
    for p in $pids; do kill_pid "$p"; done
  fi
  green "Backend stopped."
}

stop_frontend() {
  cyan "Stopping frontend..."
  if [ -f "$RUN_DIR/frontend.pid" ]; then
    kill_pid "$(cat "$RUN_DIR/frontend.pid" || true)" || true
    rm -f "$RUN_DIR/frontend.pid"
  fi
  if pids=$(pid_on_port "$FRONTEND_PORT"); [ -n "${pids}" ]; then
    for p in $pids; do kill_pid "$p"; done
  fi
  green "Frontend stopped."
}

status() {
  echo ""
  cyan "=== Status ==="
  if pids=$(pid_on_port "$BACKEND_PORT"); [ -n "${pids}" ]; then
    green "Backend: RUNNING on :$BACKEND_PORT (PID: $pids)"
  else
    red   "Backend: STOPPED"
  fi
  if pids=$(pid_on_port "$FRONTEND_PORT"); [ -n "${pids}" ]; then
    green "Frontend: RUNNING on :$FRONTEND_PORT (PID: $pids)"
  else
    red   "Frontend: STOPPED"
  fi
}

logs() {
  cyan "Tailing logs (Ctrl+C to exit)"
  touch "$LOG_DIR/backend.log" "$LOG_DIR/frontend.log"
  tail -n 50 -F "$LOG_DIR/backend.log" "$LOG_DIR/frontend.log"
}

start_all() { start_backend; start_frontend; status; }
stop_all()  { stop_frontend; stop_backend; status; }
restart_all(){ stop_all; sleep 1; start_all; }

usage() {
  cat <<EOF
VoiceCoach dev manager

Usage: $0 <command>

Commands:
  start         Start backend and frontend
  stop          Stop backend and frontend
  restart       Restart both
  status        Show process and port status
  logs          Tail both logs (50 lines)
  start:be      Start backend only
  start:fe      Start frontend only
  stop:be       Stop backend only
  stop:fe       Stop frontend only

Logs:
  $LOG_DIR/backend.log
  $LOG_DIR/frontend.log
EOF
}

cmd="${1:-}" || true
case "$cmd" in
  start)       start_all ;;
  stop)        stop_all ;;
  restart)     restart_all ;;
  status)      status ;;
  logs)        logs ;;
  start:be)    start_backend ;;
  start:fe)    start_frontend ;;
  stop:be)     stop_backend ;;
  stop:fe)     stop_frontend ;;
  ""|help|-h|--help) usage ;;
  *) red "Unknown command: $cmd"; echo ""; usage; exit 1 ;;
esac


