#!/usr/bin/env python3
"""
Cross-platform server launcher for GhostNet SSS Sentinel.
Works on Windows, Linux, and macOS.
"""
import os
import sys
import time
import socket
import tempfile
import platform
import subprocess

PROJ_DIR = os.path.dirname(os.path.abspath(__file__))
os.chdir(PROJ_DIR)


def is_port_in_use(port: int, host: str = "127.0.0.1") -> bool:
    """Check if the given port is already occupied."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex((host, port)) == 0


def kill_existing_server(port: int = 8000) -> None:
    """Safely terminate any existing uvicorn server on the port."""
    try:
        import psutil  # type: ignore
        for proc in psutil.process_iter(["pid", "name", "cmdline"]):
            try:
                cmdline = " ".join(proc.info.get("cmdline") or [])
                if "uvicorn" in cmdline and "app.main:app" in cmdline:
                    proc.terminate()
                    proc.wait(timeout=2)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.TimeoutExpired):
                pass
    except ImportError:
        # Fallback if psutil is not available
        if platform.system() == "Windows":
            subprocess.run(
                ["powershell", "-Command", f"Get-Process | Where-Object {{ $_.CommandLine -like '*uvicorn*app.main*' }} | Stop-Process -Force"],
                capture_output=True,
            )
        else:
            subprocess.run(["pkill", "-f", "uvicorn app.main"], capture_output=True)

    # Wait briefly for socket release
    for _ in range(5):
        if not is_port_in_use(port):
            break
        time.sleep(0.4)


def main():
    kill_existing_server(8000)

    # Cross-platform log file destination
    log_dir = os.path.join(PROJ_DIR, "storage")
    os.makedirs(log_dir, exist_ok=True)
    log_path = os.path.join(log_dir, "ghostnet.log")
    log_file = open(log_path, "w", encoding="utf-8")

    is_windows = platform.system() == "Windows"
    cmd = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

    popen_kwargs = {
        "stdout": log_file,
        "stderr": subprocess.STDOUT,
    }

    if is_windows:
        # On Windows, DETACHED_PROCESS creates a detached console process
        DETACHED_PROCESS = 0x00000008
        CREATE_NEW_PROCESS_GROUP = 0x00000200
        popen_kwargs["creationflags"] = DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    else:
        popen_kwargs["start_new_session"] = True

    proc = subprocess.Popen(cmd, **popen_kwargs)

    print("==================================================")
    print("  GHOSTNET SSS SENTINEL - Server Started")
    print(f"  PID:  {proc.pid}")
    print(f"  Logs: {log_path}")
    print("==================================================")
    print("  Landing:   http://localhost:8000/")
    print("  Dashboard: http://localhost:8000/dashboard")
    print("  Batch:     http://localhost:8000/batch")
    print("  API Docs:  http://localhost:8000/docs")
    print("  Health:    http://localhost:8000/health")
    print("==================================================")


if __name__ == "__main__":
    main()
