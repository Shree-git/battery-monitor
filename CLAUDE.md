# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

Battery Monitor is a macOS battery monitoring system that collects metrics every 60 seconds via launchd, stores data in SQLite, and provides CLI tools plus a React-based dashboard for analysis.

## Commands

```bash
# Installation
./install.sh
./uninstall.sh

# CLI
battery                     # Current status
battery stats -d 7          # Stats from last 7 days
battery apps -d 14          # App impact analysis
battery sessions            # Discharge session history
battery health              # Battery health analysis
battery export -o data.json # Export to JSON

# Service control
launchctl stop com.battery-monitor.daemon
launchctl start com.battery-monitor.daemon

# Development
python3 battery_collector.py      # Test data collection
python3 battery_daemon.py once    # Single snapshot
python3 battery_daemon.py start -f  # Foreground mode
```

## Architecture

```
battery_collector.py   ->  Gathers metrics using ioreg/pmset/top
        |
battery_daemon.py      ->  Background service, launchd managed
        |
battery_database.py    ->  SQLite storage (snapshots, apps, assertions, sessions)
        |
battery_cli.py         ->  Terminal interface with ANSI colors
dashboard.html         ->  Standalone React+Recharts visualization
```

## Key Details

- Python 3 stdlib only (no pip dependencies)
- macOS commands: `ioreg -rn AppleSmartBattery`, `pmset -g batt`, `pmset -g assertions`, `top -l 1`
- Database: `~/.battery_monitor/battery.db`
- CLI: `~/.local/bin/battery`
- launchd plist: `~/Library/LaunchAgents/com.battery-monitor.daemon.plist`

## Database Schema

- `snapshots`: Core metrics (percentage, wattage, temp, health, etc.)
- `active_apps`: Apps running during each snapshot
- `power_assertions`: Apps preventing sleep
- `discharge_sessions`: Complete drain cycles with rates
