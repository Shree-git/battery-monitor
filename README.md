# Battery Monitor for macOS

Lightweight battery monitoring daemon for MacBook that collects metrics, stores them in SQLite, and provides CLI tools plus a visual dashboard.

## Features

- Background daemon collects data every 60 seconds via launchd
- SQLite storage with no external dependencies
- App impact analysis and power assertion tracking
- Discharge session analysis with drain rates
- React-based visual dashboard
- CLI interface for quick access

## Installation

```bash
./install.sh
```

## Usage

```bash
battery                    # Current status
battery stats -d 7         # Stats from last 7 days
battery apps -d 14         # App impact analysis
battery sessions           # Discharge session history
battery history -H 48      # Last 48 hours of snapshots
battery health             # Battery health analysis
battery export -o data.json  # Export to JSON
```

## Visual Dashboard

```bash
battery export -o battery_data.json
open ~/.battery_monitor/dashboard.html
```

Upload the JSON file to view charts and analytics.

## Data Collected

Every 60 seconds:

- Battery percentage, charging state, cycle count
- Health percentage (max capacity / design capacity)
- Voltage, amperage, wattage, temperature
- CPU usage, display brightness
- Running applications
- Power assertions (apps preventing sleep)

## Service Management

```bash
launchctl stop com.battery-monitor.daemon
launchctl start com.battery-monitor.daemon
```

## File Locations

| Path | Description |
|------|-------------|
| `~/.battery_monitor/` | Installation directory |
| `~/.battery_monitor/battery.db` | SQLite database |
| `~/.battery_monitor/dashboard.html` | Visual dashboard |
| `~/.local/bin/battery` | CLI command |

## How It Works

```
battery_collector.py  -> Gathers metrics via ioreg/pmset/top
battery_daemon.py     -> Background service (launchd managed)
battery_database.py   -> SQLite storage
battery_cli.py        -> Terminal interface
dashboard.html        -> React visualization
```

## Uninstall

```bash
./uninstall.sh
```

## Privacy

All data is stored locally. Nothing is sent to any server.

## License

AGPL-3.0
