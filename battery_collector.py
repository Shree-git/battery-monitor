#!/usr/bin/env python3
"""
Battery Data Collector for macOS
Collects comprehensive battery metrics using native macOS commands.
"""

import subprocess
import re
import json
from datetime import datetime
from dataclasses import dataclass, asdict
from typing import Optional, Dict, Any, List


@dataclass
class BatterySnapshot:
    """Complete snapshot of battery state at a point in time."""
    timestamp: str
    
    # Core metrics
    percentage: int
    is_charging: bool
    is_plugged_in: bool
    time_remaining_minutes: Optional[int]
    
    # Health metrics
    cycle_count: int
    design_capacity_mah: int
    max_capacity_mah: int
    current_capacity_mah: int
    health_percentage: float
    
    # Power metrics
    voltage_mv: int
    amperage_ma: int
    wattage: float
    temperature_celsius: float
    
    # System state
    cpu_usage_percent: float
    active_apps: List[str]
    display_brightness: int
    
    # Power assertions (apps preventing sleep)
    power_assertions: List[Dict[str, str]]


def run_command(cmd: str) -> str:
    """Execute a shell command and return output."""
    try:
        result = subprocess.run(
            cmd, shell=True, capture_output=True, text=True, timeout=10
        )
        return result.stdout
    except Exception as e:
        return ""


def convert_signed_int64(value: int) -> int:
    """Convert unsigned 64-bit integer to signed (two's complement)."""
    if value > 2**63:
        return value - 2**64
    return value


def parse_power_details(output: str) -> Optional[float]:
    """Parse wattage from PowerOutDetails nested structure."""
    match = re.search(r'"PowerOutDetails"\s*=\s*\([^)]*"Watts"\s*=\s*(\d+)', output)
    if match:
        return int(match.group(1)) / 1000.0
    return None


def parse_ioreg_battery() -> Dict[str, Any]:
    """Parse battery info from ioreg."""
    output = run_command("ioreg -rn AppleSmartBattery")
    data = {}
    
    patterns = {
        'CycleCount': r'"CycleCount"\s*=\s*(\d+)',
        'DesignCapacity': r'"DesignCapacity"\s*=\s*(\d+)',
        'MaxCapacity': r'"MaxCapacity"\s*=\s*(\d+)',
        'AppleRawMaxCapacity': r'"AppleRawMaxCapacity"\s*=\s*(\d+)',
        'NominalChargeCapacity': r'"NominalChargeCapacity"\s*=\s*(\d+)',
        'CurrentCapacity': r'"CurrentCapacity"\s*=\s*(\d+)',
        'AppleRawCurrentCapacity': r'"AppleRawCurrentCapacity"\s*=\s*(\d+)',
        'Voltage': r'"Voltage"\s*=\s*(\d+)',
        'Amperage': r'"Amperage"\s*=\s*(\d+)',
        'Temperature': r'"Temperature"\s*=\s*(\d+)',
        'IsCharging': r'"IsCharging"\s*=\s*(Yes|No)',
        'ExternalConnected': r'"ExternalConnected"\s*=\s*(Yes|No)',
        'TimeRemaining': r'"TimeRemaining"\s*=\s*(\d+)',
    }
    
    for key, pattern in patterns.items():
        match = re.search(pattern, output)
        if match:
            value = match.group(1)
            if value in ('Yes', 'No'):
                data[key] = value == 'Yes'
            else:
                data[key] = int(value)
    
    return data


def parse_pmset_battery() -> Dict[str, Any]:
    """Parse battery info from pmset."""
    output = run_command("pmset -g batt")
    data = {'percentage': 0, 'source': 'unknown'}
    
    # Parse percentage
    match = re.search(r'(\d+)%', output)
    if match:
        data['percentage'] = int(match.group(1))
    
    # Parse power source
    if 'AC Power' in output:
        data['source'] = 'ac'
    elif 'Battery Power' in output:
        data['source'] = 'battery'
    
    # Parse time remaining
    time_match = re.search(r'(\d+):(\d+) remaining', output)
    if time_match:
        hours, mins = int(time_match.group(1)), int(time_match.group(2))
        data['time_remaining'] = hours * 60 + mins
    
    return data


def get_cpu_usage() -> float:
    """Get current CPU usage percentage."""
    output = run_command("top -l 1 -n 0 | grep 'CPU usage'")
    match = re.search(r'(\d+\.?\d*)% user.*?(\d+\.?\d*)% sys', output)
    if match:
        return float(match.group(1)) + float(match.group(2))
    return 0.0


def get_display_brightness() -> int:
    """Get display brightness percentage."""
    output = run_command("brightness -l 2>/dev/null | grep 'display 0'")
    match = re.search(r'brightness\s+(\d+\.?\d*)', output)
    if match:
        return int(float(match.group(1)) * 100)
    return -1


def get_active_apps() -> List[str]:
    """Get list of currently running user applications."""
    output = run_command(
        "ps aux | grep -v grep | awk '{print $11}' | "
        "grep -E '^/Applications|^/System/Applications' | "
        "xargs -I {} basename {} .app | sort -u | head -20"
    )
    apps = [app.strip() for app in output.split('\n') if app.strip()]
    return apps


def get_power_assertions() -> List[Dict[str, str]]:
    """Get apps preventing sleep/idle."""
    output = run_command("pmset -g assertions")
    assertions = []
    
    # Parse assertion details
    for match in re.finditer(
        r'pid (\d+)\(([^)]+)\):\s*\[([^\]]+)\]\s*(\d+:\d+:\d+)\s+(.+)',
        output
    ):
        assertions.append({
            'pid': match.group(1),
            'process': match.group(2),
            'type': match.group(3),
            'duration': match.group(4),
            'reason': match.group(5).strip()
        })
    
    return assertions


def get_top_energy_consumers() -> List[Dict[str, Any]]:
    """Get processes consuming the most energy."""
    output = run_command(
        "top -l 1 -n 10 -o power -stats pid,command,cpu,power"
    )
    consumers = []
    
    for line in output.split('\n'):
        parts = line.split()
        if len(parts) >= 4 and parts[0].isdigit():
            try:
                consumers.append({
                    'pid': int(parts[0]),
                    'command': parts[1],
                    'cpu': float(parts[2]) if parts[2].replace('.', '').isdigit() else 0,
                })
            except ValueError:
                continue
    
    return consumers[:10]


def collect_battery_snapshot() -> BatterySnapshot:
    """Collect a complete battery snapshot."""
    ioreg_output = run_command("ioreg -rn AppleSmartBattery")
    ioreg = parse_ioreg_battery()
    pmset = parse_pmset_battery()

    # Use raw capacity values (mAh), falling back to legacy fields
    design_cap = ioreg.get('DesignCapacity', 1)
    max_cap = (ioreg.get('AppleRawMaxCapacity') or
               ioreg.get('NominalChargeCapacity') or
               design_cap)
    current_cap = ioreg.get('AppleRawCurrentCapacity') or ioreg.get('CurrentCapacity', 0)

    # Health calculation using actual mAh values
    health_pct = (max_cap / design_cap * 100) if design_cap > 0 else 100.0

    voltage = ioreg.get('Voltage', 0) / 1000  # Convert to V

    # Handle amperage with two's complement conversion
    raw_amperage = ioreg.get('Amperage', 0)
    amperage_signed = convert_signed_int64(raw_amperage)
    amperage = amperage_signed / 1000  # Convert to A

    # Calculate wattage - try PowerOutDetails first, then calculate
    wattage = parse_power_details(ioreg_output)
    if wattage is None:
        wattage = abs(voltage * amperage)

    # Temperature is in centidegrees
    temp = ioreg.get('Temperature', 2500) / 100

    return BatterySnapshot(
        timestamp=datetime.now().isoformat(),
        percentage=pmset.get('percentage', 0),
        is_charging=ioreg.get('IsCharging', False),
        is_plugged_in=ioreg.get('ExternalConnected', False),
        time_remaining_minutes=pmset.get('time_remaining'),
        cycle_count=ioreg.get('CycleCount', 0),
        design_capacity_mah=design_cap,
        max_capacity_mah=max_cap,
        current_capacity_mah=current_cap,
        health_percentage=round(health_pct, 1),
        voltage_mv=ioreg.get('Voltage', 0),
        amperage_ma=amperage_signed,
        wattage=round(wattage, 2),
        temperature_celsius=round(temp, 1),
        cpu_usage_percent=round(get_cpu_usage(), 1),
        active_apps=get_active_apps(),
        display_brightness=get_display_brightness(),
        power_assertions=get_power_assertions()
    )


def snapshot_to_dict(snapshot: BatterySnapshot) -> Dict[str, Any]:
    """Convert snapshot to dictionary."""
    return asdict(snapshot)


def parse_pmset_log() -> List[Dict[str, Any]]:
    """Parse pmset log to extract historical battery events."""
    output = run_command("pmset -g log")
    events = []

    # Pattern for lines with battery info
    # Format: 2025-12-30 20:08:05 -0500 Sleep  Entering Sleep... Using Batt (Charge:99%)
    pattern = re.compile(
        r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}\s+[+-]\d{4})\s+'  # Timestamp with TZ
        r'(\w+)\s+'  # Event type (Sleep, Wake, DarkWake, Assertions, etc.)
        r'.*?'  # Message content
        r'Using\s+(Batt|AC|BATT)'  # Power source
        r'.*?\(Charge:\s*(\d+)%?\)'  # Battery percentage
    )

    for line in output.split('\n'):
        match = pattern.search(line)
        if match:
            timestamp_str = match.group(1)
            event_type = match.group(2)
            power_source = match.group(3).lower()
            percentage = int(match.group(4))

            # Parse timestamp with timezone
            # Format: 2025-12-30 20:08:05 -0500
            try:
                from datetime import timezone, timedelta as td
                # Parse manually since strptime %z can be finicky
                parts = timestamp_str.rsplit(' ', 1)
                dt_part = parts[0]
                tz_part = parts[1]
                dt = datetime.strptime(dt_part, '%Y-%m-%d %H:%M:%S')
                # Parse timezone offset
                tz_sign = 1 if tz_part[0] == '+' else -1
                tz_hours = int(tz_part[1:3])
                tz_mins = int(tz_part[3:5])
                tz_offset = td(hours=tz_hours, minutes=tz_mins) * tz_sign
                dt = dt.replace(tzinfo=timezone(tz_offset))
                iso_timestamp = dt.isoformat()
            except (ValueError, IndexError):
                continue

            events.append({
                'timestamp': iso_timestamp,
                'event_type': event_type,
                'percentage': percentage,
                'is_charging': power_source == 'ac',
                'is_plugged_in': power_source == 'ac',
            })

    return events


if __name__ == "__main__":
    # Test collection
    snapshot = collect_battery_snapshot()
    print(json.dumps(snapshot_to_dict(snapshot), indent=2))
