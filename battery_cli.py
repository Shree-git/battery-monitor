#!/usr/bin/env python3
"""
Battery Monitor CLI
Command-line interface for viewing battery statistics and insights.
"""

import argparse
import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from battery_collector import collect_battery_snapshot, snapshot_to_dict
from battery_database import BatteryDatabase


# ANSI color codes
class Colors:
    HEADER = '\033[95m'
    BLUE = '\033[94m'
    CYAN = '\033[96m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RESET = '\033[0m'


def colored(text: str, color: str) -> str:
    """Apply ANSI color to text."""
    return f"{color}{text}{Colors.RESET}"


def format_percentage_bar(pct: float, width: int = 20) -> str:
    """Create a visual percentage bar."""
    filled = int(pct / 100 * width)
    empty = width - filled
    
    if pct > 50:
        color = Colors.GREEN
    elif pct > 20:
        color = Colors.YELLOW
    else:
        color = Colors.RED
    
    bar = f"{color}{'█' * filled}{'░' * empty}{Colors.RESET}"
    return f"[{bar}] {pct:.1f}%"


def cmd_status(db: BatteryDatabase, args):
    """Show current battery status."""
    print(colored("\n⚡ Current Battery Status", Colors.BOLD + Colors.CYAN))
    print("─" * 50)
    
    snapshot = collect_battery_snapshot()
    
    # Main status
    status_icon = "🔌" if snapshot.is_charging else "🔋"
    status_text = "Charging" if snapshot.is_charging else "On Battery"
    
    print(f"\n{status_icon} Status: {colored(status_text, Colors.GREEN if snapshot.is_charging else Colors.YELLOW)}")
    print(f"   {format_percentage_bar(snapshot.percentage)}")
    
    if snapshot.time_remaining_minutes and not snapshot.is_charging:
        hours = snapshot.time_remaining_minutes // 60
        mins = snapshot.time_remaining_minutes % 60
        print(f"   ⏱️  Remaining: {hours}h {mins}m")
    
    print(f"\n📊 Metrics:")
    print(f"   Power:    {snapshot.wattage:.1f}W {'(charging)' if snapshot.amperage_ma > 0 else '(draining)'}")
    print(f"   Temp:     {snapshot.temperature_celsius:.1f}°C")
    print(f"   CPU:      {snapshot.cpu_usage_percent:.1f}%")
    if snapshot.display_brightness >= 0:
        print(f"   Display:  {snapshot.display_brightness}%")
    
    print(f"\n🏥 Battery Health:")
    print(f"   {format_percentage_bar(snapshot.health_percentage)}")
    print(f"   Cycles:   {snapshot.cycle_count}")
    print(f"   Capacity: {snapshot.max_capacity_mah}/{snapshot.design_capacity_mah} mAh")
    
    # Power assertions
    if snapshot.power_assertions:
        print(f"\n⚠️  {colored('Apps Preventing Sleep:', Colors.YELLOW)}")
        for assertion in snapshot.power_assertions[:5]:
            reason = assertion['reason']
            if len(reason) > 50:
                reason = reason[:47] + "..."
            print(f"   • {assertion['process']}: {reason}")
    
    print()


def cmd_stats(db: BatteryDatabase, args):
    """Show battery statistics."""
    print(colored(f"\n📈 Battery Statistics (Last {args.days} Days)", Colors.BOLD + Colors.CYAN))
    print("─" * 60)
    
    # Summary
    summary = db.get_summary_stats()
    print(f"\n📊 Overall:")
    print(f"   Total snapshots: {summary.get('total_snapshots', 0):,}")
    first_snapshot = summary.get('first_snapshot') or 'N/A'
    print(f"   First record:    {first_snapshot[:10]}")
    cycles = summary.get('current_cycles')
    print(f"   Battery cycles:  {cycles if cycles is not None else 'N/A'}")
    avg_wattage = summary.get('avg_discharge_wattage') or 0
    print(f"   Avg drain power: {avg_wattage:.1f}W")
    
    # Daily stats
    daily = db.get_daily_stats(args.days)
    if daily:
        print(f"\n📅 Daily Breakdown:")
        print(f"   {'Date':<12} {'Min%':>6} {'Max%':>6} {'Avg W':>7} {'Samples':>8}")
        print("   " + "-" * 45)
        for day in daily[:10]:
            avg_w = day['avg_wattage'] or 0
            print(f"   {day['date']:<12} {day['min_percentage']:>5}% "
                  f"{day['max_percentage']:>5}% {avg_w:>6.1f}W "
                  f"{day['sample_count']:>8}")
    
    # Drain patterns by hour
    patterns = db.get_drain_patterns()
    if patterns:
        print(f"\n⏰ Hourly Drain Patterns:")
        print(f"   {'Hour':>6} {'Avg Drain':>12} {'Avg Power':>12} {'Samples':>10}")
        print("   " + "-" * 45)
        for p in patterns:
            if p['samples'] > 5:
                drain = abs(p['avg_drain_per_sample'] or 0)
                avg_w = p['avg_wattage'] or 0
                print(f"   {p['hour']:>4}:00 {drain:>10.2f}%/h "
                      f"{avg_w:>10.1f}W {p['samples']:>10}")
    
    print()


def cmd_apps(db: BatteryDatabase, args):
    """Show apps correlated with battery drain."""
    print(colored(f"\n📱 App Battery Impact (Last {args.days} Days)", Colors.BOLD + Colors.CYAN))
    print("─" * 60)
    
    apps = db.get_app_frequency(args.days)
    if apps:
        print(f"\n{'App':<30} {'Times Active':>12} {'Avg Power':>10}")
        print("-" * 55)
        for app in apps[:15]:
            wattage = app['avg_wattage_when_active'] or 0
            color = Colors.RED if wattage > 15 else Colors.YELLOW if wattage > 8 else Colors.GREEN
            print(f"{app['app_name']:<30} {app['frequency']:>12} "
                  f"{colored(f'{wattage:>8.1f}W', color)}")
    else:
        print("\nNo app data available yet. Run the monitor for a while first.")
    
    # Power assertions
    assertions = db.get_power_assertion_stats(args.days)
    if assertions:
        print(f"\n⚠️  Apps Preventing Sleep:")
        print(f"   {'Process':<25} {'Type':<20} {'Frequency':>10}")
        print("   " + "-" * 55)
        for a in assertions[:10]:
            print(f"   {a['process']:<25} {a['assertion_type']:<20} {a['frequency']:>10}")
    
    print()


def cmd_sessions(db: BatteryDatabase, args):
    """Show discharge sessions."""
    print(colored(f"\n🔋 Discharge Sessions (Last {args.days} Days)", Colors.BOLD + Colors.CYAN))
    print("─" * 70)
    
    sessions = db.get_discharge_sessions(args.days)
    if sessions:
        print(f"\n{'Start':<20} {'Duration':>10} {'Drain':>8} {'Rate':>10} {'Avg Power':>10}")
        print("-" * 65)
        for s in sessions[:20]:
            start = s['start_time'][:16].replace('T', ' ')
            duration = f"{s['duration_minutes']}m" if s['duration_minutes'] else "?"
            drain = f"{s['start_percentage'] - (s['end_percentage'] or 0)}%"
            rate = f"{s['drain_rate_per_hour']:.1f}%/h" if s['drain_rate_per_hour'] else "?"
            power = f"{s['avg_wattage']:.1f}W" if s['avg_wattage'] else "?"
            
            color = Colors.RED if (s['drain_rate_per_hour'] or 0) > 20 else Colors.GREEN
            print(f"{start:<20} {duration:>10} {drain:>8} "
                  f"{colored(rate, color):>18} {power:>10}")
    else:
        print("\nNo discharge sessions recorded yet.")
    
    print()


def cmd_export(db: BatteryDatabase, args):
    """Export data to JSON."""
    output = args.output or f"battery_export_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    db.export_to_json(output, args.days)
    print(f"✅ Exported data to: {output}")


def cmd_history(db: BatteryDatabase, args):
    """Show recent snapshots."""
    print(colored(f"\n📜 Recent Battery History (Last {args.hours} Hours)", Colors.BOLD + Colors.CYAN))
    print("─" * 70)
    
    snapshots = db.get_snapshots_last_hours(args.hours)
    if snapshots:
        print(f"\n{'Time':<20} {'%':>5} {'Power':>8} {'Temp':>7} {'CPU':>6} {'Status':>10}")
        print("-" * 65)
        for s in snapshots[-30:]:  # Last 30
            time_str = s['timestamp'][11:19]
            status = "⚡Charge" if s['is_charging'] else "🔋Drain"
            print(f"{s['timestamp'][:10]} {time_str} {s['percentage']:>4}% "
                  f"{s['wattage']:>6.1f}W {s['temperature_celsius']:>5.1f}°C "
                  f"{s['cpu_usage_percent']:>5.1f}% {status:>10}")
    else:
        print("\nNo history available yet. Start the daemon to collect data.")
    
    print()


def cmd_health(db: BatteryDatabase, args):
    """Show battery health analysis."""
    print(colored("\n🏥 Battery Health Analysis", Colors.BOLD + Colors.CYAN))
    print("─" * 50)
    
    snapshot = collect_battery_snapshot()
    summary = db.get_summary_stats()
    
    # Current health
    health = snapshot.health_percentage
    if health > 90:
        health_status = colored("Excellent", Colors.GREEN)
        advice = "Your battery is in great condition!"
    elif health > 80:
        health_status = colored("Good", Colors.GREEN)
        advice = "Normal wear. Battery is healthy."
    elif health > 70:
        health_status = colored("Fair", Colors.YELLOW)
        advice = "Consider calibrating or reducing charge cycles."
    else:
        health_status = colored("Poor", Colors.RED)
        advice = "Battery may need replacement soon."
    
    print(f"\n🔋 Health: {format_percentage_bar(health)}")
    print(f"   Status: {health_status}")
    print(f"   Advice: {advice}")
    
    print(f"\n📊 Capacity:")
    print(f"   Design:  {snapshot.design_capacity_mah} mAh")
    print(f"   Current: {snapshot.max_capacity_mah} mAh")
    print(f"   Lost:    {snapshot.design_capacity_mah - snapshot.max_capacity_mah} mAh")
    
    print(f"\n🔄 Cycle Count: {snapshot.cycle_count}")
    
    # Apple rates batteries for ~1000 cycles
    cycle_health = max(0, 100 - (snapshot.cycle_count / 10))
    print(f"   Expected life: ~1000 cycles")
    print(f"   Cycle progress: {format_percentage_bar(snapshot.cycle_count / 10)}")
    
    # Temperature analysis
    sessions = db.get_discharge_sessions(30)
    if sessions:
        avg_temp = summary.get('avg_temp', 35)
        print(f"\n🌡️  Temperature Analysis:")
        if avg_temp and avg_temp > 35:
            print(f"   {colored('Warning:', Colors.YELLOW)} Average temp ({avg_temp:.1f}°C) is high.")
            print("   High temperatures degrade battery faster.")
        else:
            print(f"   Average operating temperature: {avg_temp:.1f}°C (Good)")
    
    print()


def cmd_import_history(db: BatteryDatabase, args):
    """Import historical battery data from pmset log."""
    from battery_collector import parse_pmset_log

    print(colored("\n📥 Importing Historical Battery Data", Colors.BOLD + Colors.CYAN))
    print("─" * 50)

    print("\nParsing pmset log...")
    events = parse_pmset_log()

    if not events:
        print(colored("\nNo battery events found in pmset log.", Colors.YELLOW))
        return

    print(f"Found {len(events)} battery events in system log.")

    # Show date range
    if events:
        first_ts = events[0]['timestamp'][:10]
        last_ts = events[-1]['timestamp'][:10]
        print(f"Date range: {first_ts} to {last_ts}")

    if not args.yes:
        confirm = input("\nImport these events? [y/N]: ")
        if confirm.lower() != 'y':
            print("Import cancelled.")
            return

    imported, skipped = db.import_historical_snapshots(
        events,
        avoid_duplicates=not args.force
    )

    print(colored(f"\n✅ Imported: {imported} events", Colors.GREEN))
    if skipped:
        print(colored(f"⏭️  Skipped (duplicates): {skipped} events", Colors.YELLOW))

    print()


def main():
    parser = argparse.ArgumentParser(
        description="Battery Monitor CLI for macOS",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  status         Current battery status (live)
  stats          Historical statistics
  apps           Apps correlated with battery drain
  sessions       Discharge session analysis
  history        Recent snapshot history
  health         Battery health analysis
  export         Export data to JSON
  import-history Import historical data from macOS logs

Examples:
  battery status              Show current status
  battery stats -d 7          Stats from last 7 days
  battery apps -d 14          App impact over 14 days
  battery export -o data.json Export data
  battery import-history      Import ~15 days of history from pmset log
        """
    )
    
    subparsers = parser.add_subparsers(dest='command', help='Command to run')
    
    # Status command
    sub_status = subparsers.add_parser('status', help='Current battery status')
    
    # Stats command
    sub_stats = subparsers.add_parser('stats', help='Battery statistics')
    sub_stats.add_argument('-d', '--days', type=int, default=30, help='Days to analyze')
    
    # Apps command
    sub_apps = subparsers.add_parser('apps', help='App battery impact')
    sub_apps.add_argument('-d', '--days', type=int, default=7, help='Days to analyze')
    
    # Sessions command
    sub_sessions = subparsers.add_parser('sessions', help='Discharge sessions')
    sub_sessions.add_argument('-d', '--days', type=int, default=30, help='Days to show')
    
    # History command
    sub_history = subparsers.add_parser('history', help='Recent history')
    sub_history.add_argument('-H', '--hours', type=int, default=24, help='Hours to show')
    
    # Health command
    sub_health = subparsers.add_parser('health', help='Battery health analysis')
    
    # Export command
    sub_export = subparsers.add_parser('export', help='Export data to JSON')
    sub_export.add_argument('-o', '--output', help='Output file path')
    sub_export.add_argument('-d', '--days', type=int, default=30, help='Days to export')

    # Import history command
    sub_import = subparsers.add_parser('import-history', help='Import historical battery data')
    sub_import.add_argument('-y', '--yes', action='store_true', help='Skip confirmation')
    sub_import.add_argument('-f', '--force', action='store_true', help='Import even if duplicates exist')

    args = parser.parse_args()
    
    if not args.command:
        args.command = 'status'
    
    db = BatteryDatabase()
    
    commands = {
        'status': cmd_status,
        'stats': cmd_stats,
        'apps': cmd_apps,
        'sessions': cmd_sessions,
        'history': cmd_history,
        'health': cmd_health,
        'export': cmd_export,
        'import-history': cmd_import_history,
    }
    
    if args.command in commands:
        commands[args.command](db, args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
