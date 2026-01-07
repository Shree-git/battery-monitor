#!/usr/bin/env python3
"""
Battery Database Module
Handles SQLite storage for battery metrics with efficient querying.
"""

import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from contextlib import contextmanager


class BatteryDatabase:
    """SQLite database for battery metrics storage and analysis."""
    
    def __init__(self, db_path: str = "~/.battery_monitor/battery.db"):
        self.db_path = Path(db_path).expanduser()
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()
    
    @contextmanager
    def get_connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()
    
    def _init_database(self):
        """Initialize database schema."""
        with self.get_connection() as conn:
            conn.executescript("""
                -- Main snapshots table
                CREATE TABLE IF NOT EXISTS snapshots (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT NOT NULL,
                    percentage INTEGER NOT NULL,
                    is_charging INTEGER NOT NULL,
                    is_plugged_in INTEGER NOT NULL,
                    time_remaining_minutes INTEGER,
                    cycle_count INTEGER,
                    design_capacity_mah INTEGER,
                    max_capacity_mah INTEGER,
                    current_capacity_mah INTEGER,
                    health_percentage REAL,
                    voltage_mv INTEGER,
                    amperage_ma INTEGER,
                    wattage REAL,
                    temperature_celsius REAL,
                    cpu_usage_percent REAL,
                    display_brightness INTEGER,
                    created_at TEXT DEFAULT CURRENT_TIMESTAMP
                );
                
                -- Active apps during snapshot
                CREATE TABLE IF NOT EXISTS active_apps (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_id INTEGER NOT NULL,
                    app_name TEXT NOT NULL,
                    FOREIGN KEY (snapshot_id) REFERENCES snapshots(id)
                );
                
                -- Power assertions (apps preventing sleep)
                CREATE TABLE IF NOT EXISTS power_assertions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    snapshot_id INTEGER NOT NULL,
                    pid TEXT,
                    process TEXT,
                    assertion_type TEXT,
                    duration TEXT,
                    reason TEXT,
                    FOREIGN KEY (snapshot_id) REFERENCES snapshots(id)
                );
                
                -- Discharge sessions for tracking battery drain patterns
                CREATE TABLE IF NOT EXISTS discharge_sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    start_percentage INTEGER NOT NULL,
                    end_percentage INTEGER,
                    duration_minutes INTEGER,
                    drain_rate_per_hour REAL,
                    avg_wattage REAL,
                    avg_cpu_usage REAL,
                    is_active INTEGER DEFAULT 1
                );
                
                -- Indexes for common queries
                CREATE INDEX IF NOT EXISTS idx_snapshots_timestamp 
                    ON snapshots(timestamp);
                CREATE INDEX IF NOT EXISTS idx_snapshots_percentage 
                    ON snapshots(percentage);
                CREATE INDEX IF NOT EXISTS idx_active_apps_snapshot 
                    ON active_apps(snapshot_id);
                CREATE INDEX IF NOT EXISTS idx_assertions_snapshot 
                    ON power_assertions(snapshot_id);
            """)
    
    def insert_snapshot(self, snapshot: Dict[str, Any]) -> int:
        """Insert a battery snapshot and return its ID."""
        with self.get_connection() as conn:
            cursor = conn.execute("""
                INSERT INTO snapshots (
                    timestamp, percentage, is_charging, is_plugged_in,
                    time_remaining_minutes, cycle_count, design_capacity_mah,
                    max_capacity_mah, current_capacity_mah, health_percentage,
                    voltage_mv, amperage_ma, wattage, temperature_celsius,
                    cpu_usage_percent, display_brightness
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                snapshot['timestamp'],
                snapshot['percentage'],
                int(snapshot['is_charging']),
                int(snapshot['is_plugged_in']),
                snapshot.get('time_remaining_minutes'),
                snapshot.get('cycle_count'),
                snapshot.get('design_capacity_mah'),
                snapshot.get('max_capacity_mah'),
                snapshot.get('current_capacity_mah'),
                snapshot.get('health_percentage'),
                snapshot.get('voltage_mv'),
                snapshot.get('amperage_ma'),
                snapshot.get('wattage'),
                snapshot.get('temperature_celsius'),
                snapshot.get('cpu_usage_percent'),
                snapshot.get('display_brightness'),
            ))
            snapshot_id = cursor.lastrowid
            
            # Insert active apps
            for app in snapshot.get('active_apps', []):
                conn.execute(
                    "INSERT INTO active_apps (snapshot_id, app_name) VALUES (?, ?)",
                    (snapshot_id, app)
                )
            
            # Insert power assertions
            for assertion in snapshot.get('power_assertions', []):
                conn.execute("""
                    INSERT INTO power_assertions 
                    (snapshot_id, pid, process, assertion_type, duration, reason)
                    VALUES (?, ?, ?, ?, ?, ?)
                """, (
                    snapshot_id,
                    assertion.get('pid'),
                    assertion.get('process'),
                    assertion.get('type'),
                    assertion.get('duration'),
                    assertion.get('reason'),
                ))
            
            return snapshot_id
    
    def get_latest_snapshot(self) -> Optional[Dict[str, Any]]:
        """Get the most recent snapshot."""
        with self.get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM snapshots ORDER BY timestamp DESC LIMIT 1"
            ).fetchone()
            return dict(row) if row else None
    
    def get_snapshots_range(
        self, 
        start: datetime, 
        end: datetime
    ) -> List[Dict[str, Any]]:
        """Get snapshots within a time range."""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM snapshots 
                WHERE timestamp BETWEEN ? AND ?
                ORDER BY timestamp ASC
            """, (start.isoformat(), end.isoformat())).fetchall()
            return [dict(row) for row in rows]
    
    def get_snapshots_last_hours(self, hours: int) -> List[Dict[str, Any]]:
        """Get snapshots from the last N hours."""
        end = datetime.now()
        start = end - timedelta(hours=hours)
        return self.get_snapshots_range(start, end)
    
    def get_daily_stats(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get daily aggregated statistics."""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT 
                    DATE(timestamp) as date,
                    MIN(percentage) as min_percentage,
                    MAX(percentage) as max_percentage,
                    AVG(percentage) as avg_percentage,
                    AVG(wattage) as avg_wattage,
                    AVG(cpu_usage_percent) as avg_cpu,
                    AVG(temperature_celsius) as avg_temp,
                    COUNT(*) as sample_count,
                    SUM(CASE WHEN is_charging = 0 THEN 1 ELSE 0 END) as discharge_samples
                FROM snapshots
                WHERE timestamp >= DATE('now', ?)
                GROUP BY DATE(timestamp)
                ORDER BY date DESC
            """, (f'-{days} days',)).fetchall()
            return [dict(row) for row in rows]
    
    def get_app_frequency(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get frequency of apps during battery drain."""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT 
                    a.app_name,
                    COUNT(*) as frequency,
                    AVG(s.wattage) as avg_wattage_when_active,
                    AVG(s.cpu_usage_percent) as avg_cpu_when_active
                FROM active_apps a
                JOIN snapshots s ON a.snapshot_id = s.id
                WHERE s.timestamp >= DATE('now', ?)
                AND s.is_charging = 0
                GROUP BY a.app_name
                ORDER BY frequency DESC
                LIMIT 20
            """, (f'-{days} days',)).fetchall()
            return [dict(row) for row in rows]
    
    def get_power_assertion_stats(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get statistics on power assertions (apps preventing sleep)."""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT 
                    process,
                    assertion_type,
                    COUNT(*) as frequency,
                    GROUP_CONCAT(DISTINCT reason) as reasons
                FROM power_assertions p
                JOIN snapshots s ON p.snapshot_id = s.id
                WHERE s.timestamp >= DATE('now', ?)
                GROUP BY process, assertion_type
                ORDER BY frequency DESC
                LIMIT 20
            """, (f'-{days} days',)).fetchall()
            return [dict(row) for row in rows]
    
    def get_drain_patterns(self) -> List[Dict[str, Any]]:
        """Analyze battery drain patterns."""
        with self.get_connection() as conn:
            rows = conn.execute("""
                WITH consecutive AS (
                    SELECT 
                        *,
                        LAG(percentage) OVER (ORDER BY timestamp) as prev_pct,
                        LAG(timestamp) OVER (ORDER BY timestamp) as prev_ts,
                        percentage - LAG(percentage) OVER (ORDER BY timestamp) as drain
                    FROM snapshots
                    WHERE is_charging = 0
                )
                SELECT 
                    strftime('%H', timestamp) as hour,
                    AVG(drain) as avg_drain_per_sample,
                    AVG(wattage) as avg_wattage,
                    AVG(cpu_usage_percent) as avg_cpu,
                    COUNT(*) as samples
                FROM consecutive
                WHERE drain IS NOT NULL AND drain < 0
                GROUP BY strftime('%H', timestamp)
                ORDER BY hour
            """).fetchall()
            return [dict(row) for row in rows]
    
    def update_discharge_session(self, snapshot: Dict[str, Any]):
        """Track discharge sessions for detailed drain analysis."""
        with self.get_connection() as conn:
            # Get active session
            active = conn.execute(
                "SELECT * FROM discharge_sessions WHERE is_active = 1"
            ).fetchone()
            
            if snapshot['is_plugged_in'] or snapshot['is_charging']:
                # End active session if plugged in
                if active:
                    start_time = datetime.fromisoformat(active['start_time'])
                    duration = (
                        datetime.fromisoformat(snapshot['timestamp']) - start_time
                    ).total_seconds() / 60
                    
                    drain = active['start_percentage'] - snapshot['percentage']
                    drain_rate = (drain / duration * 60) if duration > 0 else 0
                    
                    # Get averages from session
                    avgs = conn.execute("""
                        SELECT AVG(wattage) as avg_w, AVG(cpu_usage_percent) as avg_cpu
                        FROM snapshots
                        WHERE timestamp BETWEEN ? AND ?
                    """, (active['start_time'], snapshot['timestamp'])).fetchone()
                    
                    conn.execute("""
                        UPDATE discharge_sessions 
                        SET end_time = ?, end_percentage = ?, duration_minutes = ?,
                            drain_rate_per_hour = ?, avg_wattage = ?, avg_cpu_usage = ?,
                            is_active = 0
                        WHERE id = ?
                    """, (
                        snapshot['timestamp'], snapshot['percentage'],
                        int(duration), round(drain_rate, 2),
                        avgs['avg_w'], avgs['avg_cpu'], active['id']
                    ))
            else:
                # Start new session or continue
                if not active:
                    conn.execute("""
                        INSERT INTO discharge_sessions 
                        (start_time, start_percentage)
                        VALUES (?, ?)
                    """, (snapshot['timestamp'], snapshot['percentage']))
    
    def get_discharge_sessions(self, days: int = 30) -> List[Dict[str, Any]]:
        """Get completed discharge sessions."""
        with self.get_connection() as conn:
            rows = conn.execute("""
                SELECT * FROM discharge_sessions
                WHERE is_active = 0
                AND start_time >= DATE('now', ?)
                ORDER BY start_time DESC
            """, (f'-{days} days',)).fetchall()
            return [dict(row) for row in rows]
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get overall summary statistics."""
        with self.get_connection() as conn:
            row = conn.execute("""
                SELECT 
                    COUNT(*) as total_snapshots,
                    MIN(timestamp) as first_snapshot,
                    MAX(timestamp) as last_snapshot,
                    MAX(cycle_count) as current_cycles,
                    AVG(health_percentage) as avg_health,
                    AVG(CASE WHEN is_charging = 0 THEN wattage END) as avg_discharge_wattage
                FROM snapshots
            """).fetchone()
            return dict(row) if row else {}
    
    def export_to_json(self, filepath: str, days: int = 30):
        """Export data to JSON file."""
        data = {
            'summary': self.get_summary_stats(),
            'daily_stats': self.get_daily_stats(days),
            'drain_patterns': self.get_drain_patterns(),
            'app_frequency': self.get_app_frequency(days),
            'power_assertions': self.get_power_assertion_stats(days),
            'discharge_sessions': self.get_discharge_sessions(days),
            'snapshots': self.get_snapshots_last_hours(days * 24),
        }
        
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)
    
    def import_historical_snapshots(
        self,
        events: List[Dict[str, Any]],
        avoid_duplicates: bool = True
    ) -> Tuple[int, int]:
        """
        Import historical snapshots from pmset log.
        Returns (imported_count, skipped_count).
        """
        imported = 0
        skipped = 0

        with self.get_connection() as conn:
            for event in events:
                # Check for duplicate if requested
                if avoid_duplicates:
                    existing = conn.execute(
                        "SELECT id FROM snapshots WHERE timestamp = ?",
                        (event['timestamp'],)
                    ).fetchone()
                    if existing:
                        skipped += 1
                        continue

                # Insert with partial data (no wattage, temp, apps, etc.)
                conn.execute("""
                    INSERT INTO snapshots (
                        timestamp, percentage, is_charging, is_plugged_in,
                        time_remaining_minutes, cycle_count, design_capacity_mah,
                        max_capacity_mah, current_capacity_mah, health_percentage,
                        voltage_mv, amperage_ma, wattage, temperature_celsius,
                        cpu_usage_percent, display_brightness
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    event['timestamp'],
                    event['percentage'],
                    int(event['is_charging']),
                    int(event['is_plugged_in']),
                    None,  # time_remaining_minutes
                    None,  # cycle_count
                    None,  # design_capacity_mah
                    None,  # max_capacity_mah
                    None,  # current_capacity_mah
                    None,  # health_percentage
                    None,  # voltage_mv
                    None,  # amperage_ma
                    None,  # wattage
                    None,  # temperature_celsius
                    None,  # cpu_usage_percent
                    None,  # display_brightness
                ))
                imported += 1

        return imported, skipped

    def cleanup_old_data(self, days_to_keep: int = 90):
        """Remove data older than specified days."""
        with self.get_connection() as conn:
            cutoff = (datetime.now() - timedelta(days=days_to_keep)).isoformat()
            conn.execute(
                "DELETE FROM power_assertions WHERE snapshot_id IN "
                "(SELECT id FROM snapshots WHERE timestamp < ?)",
                (cutoff,)
            )
            conn.execute(
                "DELETE FROM active_apps WHERE snapshot_id IN "
                "(SELECT id FROM snapshots WHERE timestamp < ?)",
                (cutoff,)
            )
            conn.execute("DELETE FROM snapshots WHERE timestamp < ?", (cutoff,))
            conn.execute("DELETE FROM discharge_sessions WHERE start_time < ?", (cutoff,))
            conn.execute("VACUUM")


if __name__ == "__main__":
    # Test database
    db = BatteryDatabase()
    print(f"Database path: {db.db_path}")
    print(f"Summary: {db.get_summary_stats()}")
