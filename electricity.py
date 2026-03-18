#!/usr/bin/env python3
"""Electricity tracking module for Seedbox Web Dashboard"""

import json
import time
import threading
from datetime import date
from config import ELEC_FILE, DEFAULT_WATTS, DEFAULT_RATE, DEFAULT_CURRENCY
from system_utils import get_system_uptime

_elec_lock = threading.Lock()
_elec_last_tick = 0
_elec_last_uptime = 0


def load_data():
    """Load electricity tracking data from file"""
    try:
        with open(ELEC_FILE) as f:
            return json.load(f)
    except Exception:
        return {"days": {}, "cfg": {"watts": DEFAULT_WATTS, "rate": DEFAULT_RATE, "currency": DEFAULT_CURRENCY}}


def save_data(data):
    """Save electricity tracking data to file"""
    try:
        with open(ELEC_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print("Warning: Could not save electricity data: {}".format(e))


def record_minute():
    """Record one minute of uptime - called every 60 seconds"""
    global _elec_last_tick, _elec_last_uptime
    
    with _elec_lock:
        data = load_data()
        today = date.today().isoformat()
        
        if "days" not in data:
            data["days"] = {}
        
        # Get current uptime
        uptime_seconds, _ = get_system_uptime()
        
        # Detect reboot or time jump
        if _elec_last_uptime > 0:
            # Expected increase: ~60 seconds
            expected_increase = 60
            actual_increase = uptime_seconds - _elec_last_uptime
            
            # If we missed more than 90 seconds, we might have had a reboot or sleep
            if actual_increase > 90 or actual_increase < 0:
                print("Detected possible reboot/sleep: last_uptime={}, current={}, diff={}".format(
                    _elec_last_uptime, uptime_seconds, actual_increase))
                # Don't record this minute as we can't be sure
        
        # Add one minute of uptime
        data["days"][today] = data["days"].get(today, 0) + 1
        
        if "since" not in data:
            data["since"] = today
        
        # Store timestamp and uptime for next check
        _elec_last_tick = time.time()
        _elec_last_uptime = uptime_seconds
        
        save_data(data)


def calculate_costs(data):
    """Calculate electricity costs from stored minutes"""
    cfg = data.get("cfg", {})
    watts = float(cfg.get("watts", DEFAULT_WATTS))
    rate = float(cfg.get("rate", DEFAULT_RATE))
    currency = str(cfg.get("currency", DEFAULT_CURRENCY))
    days = data.get("days", {})
    
    today = date.today().isoformat()
    month = today[:7]
    
    today_minutes = days.get(today, 0)
    month_minutes = sum(minutes for day, minutes in days.items() if day.startswith(month))
    total_minutes = sum(days.values())
    
    def calculate_cost(minutes):
        hours = minutes / 60
        kwh = (watts * hours) / 1000
        return round(kwh * rate, 2), round(kwh, 4)
    
    today_cost, today_kwh = calculate_cost(today_minutes)
    month_cost, month_kwh = calculate_cost(month_minutes)
    total_cost, total_kwh = calculate_cost(total_minutes)
    
    # Daily breakdown for last 30 days
    daily = []
    sorted_days = sorted(days.keys(), reverse=True)[:30]
    
    for day in sorted_days:
        day_cost, day_kwh = calculate_cost(days[day])
        hours, minutes = divmod(days[day], 60)
        daily.append({
            "date": day,
            "minutes": days[day],
            "hours_str": "{}h {}m".format(hours, minutes),
            "kwh": day_kwh,
            "cost": day_cost,
            "today": day == today,
        })
    
    # Get real uptime for display
    uptime_seconds, uptime_formatted = get_system_uptime()
    
    return {
        "today_cost": today_cost,
        "month_cost": month_cost,
        "total_cost": total_cost,
        "today_kwh": today_kwh,
        "month_kwh": month_kwh,
        "total_kwh": total_kwh,
        "today_minutes": today_minutes,
        "month_minutes": month_minutes,
        "today_hours": "{:.1f}h".format(today_minutes / 60),
        "currency": currency,
        "watts": watts,
        "rate": rate,
        "since": data.get("since", today),
        "daily": daily,
        "uptime_seconds": uptime_seconds,
        "uptime_formatted": uptime_formatted,
    }


def get_current_data():
    """Get current electricity data with lock"""
    with _elec_lock:
        data = load_data()
    return calculate_costs(data)


def save_settings(watts, rate, currency):
    """Save electricity settings"""
    with _elec_lock:
        data = load_data()
        data["cfg"] = {"watts": watts, "rate": rate, "currency": currency}
        save_data(data)


def reset_data():
    """Reset all electricity tracking data"""
    with _elec_lock:
        data = load_data()
        cfg = data.get("cfg", {})
        save_data({"days": {}, "cfg": cfg})


# Background thread to record minutes
def _ticker_thread():
    """Background thread that records a minute of uptime every 60 seconds"""
    # Wait a bit at startup
    time.sleep(5)
    
    while True:
        try:
            record_minute()
        except Exception as e:
            print("Electricity tick error: {}".format(e))
        time.sleep(60)


# Start the background thread
ticker = threading.Thread(target=_ticker_thread, daemon=True)
ticker.start()
