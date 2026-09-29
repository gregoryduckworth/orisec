# Orisec Alarm Panel for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://github.com/hacs/integration)

A [HACS](https://hacs.xyz/) custom integration that lets [Home Assistant](https://www.home-assistant.io/)
talk directly to Orisec ControlPlus alarm panels over the **local network** —
no cloud account required.

## Features

- Local polling over UDP (default port `20202`), so it keeps working even if
  your internet connection is down.
- An `alarm_control_panel` entity to arm (away/home) and disarm the panel.
- A `binary_sensor` entity per zone reporting open/closed state.
- Configuration entirely through the Home Assistant UI (Config Flow) — no
  YAML required.

## Installation

### Via HACS (recommended)

1. In Home Assistant, go to **HACS**.
2. Click the three-dot menu in the top right and choose **Custom repositories**.
3. Add this repository URL (`https://github.com/gregoryduckworth/orisec`) with
   category **Integration**.
4. Search for **Orisec Alarm Panel** in HACS and install it.
5. Restart Home Assistant.

### Manual installation

Copy the `custom_components/orisec` folder into your Home Assistant
`config/custom_components` directory and restart Home Assistant.

## Configuration

1. In Home Assistant, go to **Settings → Devices & Services → Add Integration**.
2. Search for **Orisec Alarm Panel**.
3. Enter the IP address (or hostname), port (defaults to `20202`) and the
   PIN used by your panel's keypad/app.

## Supported panels

This integration targets the Orisec ControlPlus family of panels
(CP10, CP20, CP40, CP200, EP100 and their Z-variants) that expose the local
UDP control protocol on the LAN. Some newer firmware versions disable the
local protocol in favour of cloud-only access — check with your installer if
you are unsure whether your panel supports this.

## Contributing

Issues and pull requests are welcome. Unit tests for the local network
client live under `tests/` and can be run with:

```bash
pip install -r requirements-test.txt
pytest
```
