"""Constants for the Orisec Alarm Panel integration."""
from __future__ import annotations

from datetime import timedelta

from .api import DEFAULT_TIMEOUT  # noqa: F401  (re-exported for convenience)

DOMAIN = "orisec"

CONF_HOST = "host"
CONF_PORT = "port"
CONF_PIN = "pin"

DEFAULT_PORT = 20202
DEFAULT_SCAN_INTERVAL = timedelta(seconds=10)

MANUFACTURER = "Orisec"
DEFAULT_NAME = "Orisec Alarm Panel"

# Panel arming states as reported by the coordinator.
STATE_DISARMED = "disarmed"
STATE_ARMED_AWAY = "armed_away"
STATE_ARMED_HOME = "armed_home"
STATE_TRIGGERED = "triggered"
