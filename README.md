# 🔋 Battery Monitor for macOS

A minimal, efficient battery monitoring system for MacBook Pro that collects comprehensive data to help you understand and improve battery life.

## Features

- **Real-time Monitoring**: Track battery percentage, power draw, temperature, and health
- **Background Daemon**: Automatically collects data every 60 seconds via launchd
- **SQLite Storage**: Efficient local storage with no external dependencies
- **App Impact Analysis**: See which apps correlate with high battery drain
- **Power Assertions**: Track apps preventing sleep/idle
- **Discharge Sessions**: Analyze complete drain cycles
- **Hourly Patterns**: Understand when your battery drains fastest
- **Visual Dashboard**: Beautiful React-based visualization
- **CLI Interface**: Quick access to all stats from terminal

## Quick Start

```bash
# Clone or download, then install
./install.sh

# View current status
battery

# See all commands
battery --help
```

## CLI Commands

### Status (default)
```bash
battery           # or battery status
```
Shows current battery status including charge level, power draw, temperature, health, and active power assertions.

### Statistics
```bash
battery stats              # Last 30 days
battery stats -d 7         # Last 7 days
```
Shows daily aggregated statistics and hourly drain patterns.

### App Analysis
```bash
battery apps               # Last 7 days
battery apps -d 14         # Last 14 days
```
Shows which apps are active during battery drain and their average power consumption.

### Discharge Sessions
```bash
battery sessions           # All sessions
battery sessions -d 7      # Last 7 days
```
Detailed breakdown of each battery discharge session with drain rates.

### History
```bash
battery history            # Last 24 hours
battery history -H 48      # Last 48 hours
```
Shows recent snapshots with all metrics.

### Health Analysis
```bash
battery health
```
Comprehensive battery health report with recommendations.

### Export Data
```bash
battery export                    # Default filename
battery export -o my_data.json   # Custom filename
battery export -d 7              # Last 7 days only
```
Export data to JSON for the visual dashboard or external analysis.

## Visual Dashboard

1. Export your data:
   ```bash
   battery export -o battery_data.json
   ```

2. Open the dashboard:
   ```bash
   open ~/.battery_monitor/dashboard.html
   ```

3. Click "Choose File" and upload your JSON export

The dashboard shows:
- Battery level gauge with health indicator
- Timeline chart of battery percentage
- Hourly drain patterns
- App power consumption comparison
- Discharge session history

## Data Collected

Every 60 seconds, the daemon records:

| Metric | Description |
|--------|-------------|
| `percentage` | Current charge level |
| `is_charging` | Whether plugged in and charging |
| `cycle_count` | Total charge cycles |
| `health_percentage` | Battery health (max_cap / design_cap) |
| `voltage_mv` | Battery voltage |
| `amperage_ma` | Current draw (negative = discharging) |
| `wattage` | Power in watts |
| `temperature_celsius` | Battery temperature |
| `cpu_usage_percent` | CPU utilization |
| `display_brightness` | Screen brightness level |
| `active_apps` | Running applications |
| `power_assertions` | Apps preventing sleep |

## Service Management

The daemon runs automatically via launchd. Control it with:

```bash
# Stop the service
launchctl stop com.battery-monitor.daemon

# Start the service
launchctl start com.battery-monitor.daemon

# Disable auto-start
launchctl unload ~/Library/LaunchAgents/com.battery-monitor.daemon.plist

# Re-enable auto-start
launchctl load -w ~/Library/LaunchAgents/com.battery-monitor.daemon.plist
```

## File Locations

| Path | Description |
|------|-------------|
| `~/.battery_monitor/` | Installation directory |
| `~/.battery_monitor/battery.db` | SQLite database |
| `~/.battery_monitor/battery_monitor.log` | Daemon log file |
| `~/.battery_monitor/dashboard.html` | Visual dashboard |
| `~/.local/bin/battery` | CLI command |
| `~/Library/LaunchAgents/com.battery-monitor.daemon.plist` | launchd config |

## Understanding Battery Drain

### Normal Ranges
- **Light use** (browsing, documents): 4-8W
- **Medium use** (development, video calls): 8-15W  
- **Heavy use** (compilation, gaming, video editing): 15-30W

### Common Drain Causes
1. **Chrome/Electron apps**: Often consume 10-20W
2. **Video conferencing**: Zoom, Teams can use 15-25W
3. **Compilation/Docker**: Heavy CPU = heavy drain
4. **Display brightness**: Each 20% increase ≈ 1W
5. **Background indexing**: Spotlight can spike to 10W+

### Optimization Tips
Based on your data, consider:
- Use Safari instead of Chrome for browsing
- Reduce display brightness when on battery
- Quit unused Electron apps (Slack, VS Code, etc.)
- Disable background app refresh
- Keep macOS and apps updated

## Uninstallation

```bash
./uninstall.sh
```

This removes all files and stops the service. Your battery data will be deleted.

## Technical Details

### Dependencies
- Python 3 (built into macOS)
- No pip packages required

### How It Works
1. `battery_collector.py` - Uses `ioreg`, `pmset`, and `top` to gather battery metrics
2. `battery_database.py` - Manages SQLite storage with optimized indexes
3. `battery_daemon.py` - Background service that collects data on interval
4. `battery_cli.py` - Command-line interface for viewing data
5. `dashboard.html` - React-based visualization (offline, no server needed)

### Database Schema

```sql
-- Main data table
snapshots (id, timestamp, percentage, is_charging, ...)

-- App tracking
active_apps (id, snapshot_id, app_name)

-- Power assertions (apps preventing sleep)
power_assertions (id, snapshot_id, pid, process, type, reason)

-- Discharge session analysis
discharge_sessions (id, start_time, end_time, drain_rate, ...)
```

## Privacy

All data is stored locally in SQLite. Nothing is sent to any server. The dashboard works completely offline.

## License

MIT License - Use freely, modify as needed.

---

Made with ⚡ for MacBook users who care about battery life.
