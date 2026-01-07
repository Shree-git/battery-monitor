#!/usr/bin/env python3
"""
Battery Monitor Daemon
Background service that collects battery data at regular intervals.
"""

import os
import sys
import time
import signal
import argparse
import logging
from pathlib import Path
from datetime import datetime

from battery_collector import collect_battery_snapshot, snapshot_to_dict
from battery_database import BatteryDatabase


class BatteryMonitorDaemon:
    """Background daemon for collecting battery metrics."""
    
    def __init__(
        self, 
        interval_seconds: int = 60,
        db_path: str = "~/.battery_monitor/battery.db",
        log_path: str = "~/.battery_monitor/battery_monitor.log"
    ):
        self.interval = interval_seconds
        self.db = BatteryDatabase(db_path)
        self.running = False
        self.setup_logging(log_path)
        
        # Handle shutdown signals
        signal.signal(signal.SIGTERM, self._handle_shutdown)
        signal.signal(signal.SIGINT, self._handle_shutdown)
    
    def setup_logging(self, log_path: str):
        """Configure logging."""
        log_file = Path(log_path).expanduser()
        log_file.parent.mkdir(parents=True, exist_ok=True)
        
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler(log_file),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger(__name__)
    
    def _handle_shutdown(self, signum, frame):
        """Handle shutdown signals gracefully."""
        self.logger.info(f"Received signal {signum}, shutting down...")
        self.running = False
    
    def collect_and_store(self):
        """Collect a snapshot and store it."""
        try:
            snapshot = collect_battery_snapshot()
            snapshot_dict = snapshot_to_dict(snapshot)
            
            # Store in database
            snapshot_id = self.db.insert_snapshot(snapshot_dict)
            
            # Update discharge session tracking
            self.db.update_discharge_session(snapshot_dict)
            
            self.logger.info(
                f"Snapshot #{snapshot_id}: {snapshot.percentage}% | "
                f"{snapshot.wattage}W | {snapshot.temperature_celsius}°C | "
                f"{'⚡ Charging' if snapshot.is_charging else '🔋 Discharging'}"
            )
            
            return snapshot_dict
            
        except Exception as e:
            self.logger.error(f"Error collecting snapshot: {e}")
            return None
    
    def run(self):
        """Main daemon loop."""
        self.running = True
        self.logger.info(
            f"Battery Monitor started. Collecting every {self.interval}s. "
            f"DB: {self.db.db_path}"
        )
        
        # Collect immediately on start
        self.collect_and_store()
        
        while self.running:
            time.sleep(self.interval)
            if self.running:
                self.collect_and_store()
        
        self.logger.info("Battery Monitor stopped.")
    
    def run_once(self):
        """Collect a single snapshot (useful for testing)."""
        return self.collect_and_store()


def get_pid_file() -> Path:
    """Get path to PID file."""
    return Path("~/.battery_monitor/daemon.pid").expanduser()


def is_running() -> bool:
    """Check if daemon is already running."""
    pid_file = get_pid_file()
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)  # Check if process exists
            return True
        except (ProcessLookupError, ValueError):
            pid_file.unlink()
    return False


def start_daemon(interval: int = 60, foreground: bool = False):
    """Start the daemon."""
    if is_running():
        print("Battery Monitor is already running.")
        return
    
    if not foreground:
        # Fork to background
        try:
            pid = os.fork()
            if pid > 0:
                print(f"Battery Monitor started (PID: {pid})")
                return
        except OSError as e:
            print(f"Fork failed: {e}")
            sys.exit(1)
        
        # Create new session
        os.setsid()
        
        # Fork again
        try:
            pid = os.fork()
            if pid > 0:
                sys.exit(0)
        except OSError:
            sys.exit(1)
        
        # Redirect stdout/stderr
        sys.stdout.flush()
        sys.stderr.flush()
        
        null = open('/dev/null', 'w')
        os.dup2(null.fileno(), sys.stdout.fileno())
        os.dup2(null.fileno(), sys.stderr.fileno())
    
    # Write PID file
    pid_file = get_pid_file()
    pid_file.parent.mkdir(parents=True, exist_ok=True)
    pid_file.write_text(str(os.getpid()))
    
    try:
        daemon = BatteryMonitorDaemon(interval_seconds=interval)
        daemon.run()
    finally:
        if pid_file.exists():
            pid_file.unlink()


def stop_daemon():
    """Stop the daemon."""
    pid_file = get_pid_file()
    if not pid_file.exists():
        print("Battery Monitor is not running.")
        return
    
    try:
        pid = int(pid_file.read_text().strip())
        os.kill(pid, signal.SIGTERM)
        print(f"Battery Monitor stopped (PID: {pid})")
        pid_file.unlink()
    except ProcessLookupError:
        print("Process not found. Cleaning up...")
        pid_file.unlink()
    except Exception as e:
        print(f"Error stopping daemon: {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Battery Monitor Daemon for macOS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  battery_daemon.py start           Start daemon in background
  battery_daemon.py start -f        Start in foreground (for testing)
  battery_daemon.py start -i 30     Collect every 30 seconds
  battery_daemon.py stop            Stop the daemon
  battery_daemon.py status          Check if running
  battery_daemon.py once            Collect single snapshot
        """
    )
    
    parser.add_argument(
        'command',
        choices=['start', 'stop', 'status', 'restart', 'once'],
        help='Command to execute'
    )
    parser.add_argument(
        '-i', '--interval',
        type=int,
        default=60,
        help='Collection interval in seconds (default: 60)'
    )
    parser.add_argument(
        '-f', '--foreground',
        action='store_true',
        help='Run in foreground (don\'t daemonize)'
    )
    
    args = parser.parse_args()
    
    if args.command == 'start':
        start_daemon(args.interval, args.foreground)
    
    elif args.command == 'stop':
        stop_daemon()
    
    elif args.command == 'restart':
        stop_daemon()
        time.sleep(1)
        start_daemon(args.interval, args.foreground)
    
    elif args.command == 'status':
        if is_running():
            pid = int(get_pid_file().read_text().strip())
            print(f"Battery Monitor is running (PID: {pid})")
        else:
            print("Battery Monitor is not running")
    
    elif args.command == 'once':
        daemon = BatteryMonitorDaemon()
        snapshot = daemon.run_once()
        if snapshot:
            import json
            print(json.dumps(snapshot, indent=2))


if __name__ == "__main__":
    main()
