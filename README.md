# Hako Foundry

A server chassis storage companion app that organizes and displays hard drive SMART data with integrated power management.

## Overview

Hako Foundry is a containerized application that combines drive health monitoring through SMART data analysis with hardware control capabilities via the Hako Core Powerboard. The application can function without the Hako Core Powerboard. If no powerboard is connected, you'll still have access to drive organization and SMART data monitoring. Primary development and testing is performed on TrueNAS Scale, though the application should work on other Docker-capable systems.

## Features

- **Drive Organization & Monitoring**: Centralized view of all connected hard drives with SMART data visualization
- **Fan Control**: Control individual fan walls through the Hako Core Powerboard interface

## Status

**Beta Version** - This project is currently in beta. Please report any bugs you encounter or drives that are not properly supported.

### Quick Start

Choose one of the following commands based on whether you want authentication:

**With Authentication:**
Replace 'admin' and 'pass' with your own credentials. 
```bash
docker run \
  $(ls /dev/ttyACM* | sed 's/^/--device /') \
  $(lsblk -d -n -o NAME | grep '^sd' | sed 's|^|--device /dev/|') \
  --cap-add SYS_RAWIO \
  -v foundry_config:/app/config/ \
  -e ADMIN_USERNAME='admin' \
  -e ADMIN_PASSWORD='pass' \
  -p 8080:8080 \
  hakoforge/hako-foundry
```

**Without Authentication (Open Access):**
```bash
docker run \
  $(ls /dev/ttyACM* | sed 's/^/--device /') \
  $(lsblk -d -n -o NAME | grep '^sd' | sed 's|^|--device /dev/|') \
  --cap-add SYS_RAWIO \
  -v foundry_config:/app/config/ \
  -p 8080:8080 \
  hakoforge/hako-foundry
```

### Command Breakdown

- **Powerboard Detection**: `$(ls /dev/ttyACM* | sed 's/^/--device /')` - Automatically detects and passes powerboard USB connections
  ```bash
  # Example output: --device /dev/ttyACM0 --device /dev/ttyACM1
  ```
- **Drive Detection**: `$(lsblk -d -n -o NAME | grep '^sd' | sed 's|^|--device /dev/|')` - Identifies and passes all connected drives
  ```bash
  # Example output: --device /dev/sda --device /dev/sdb --device /dev/sdc --device /dev/sdd
  ```
- **Raw I/O Access**: `--cap-add SYS_RAWIO` - Required for SMART data collection
- **Persistent Storage**: `-v foundry_config:/app/config/` - Creates a Docker volume to preserve configuration between restarts
- **Authentication**: `-e ADMIN_USERNAME` and `-e ADMIN_PASSWORD` - Optional login credentials
- **Port Mapping**: `-p 8080:8080` - Maps container port to host system

## Roadmap

### Planned Features

- **Fan Curves**: Automatic fan speed adjustment based on drive temperatures
- **Long-term Data Logging**: Historical tracking of drive attributes and power usage
- **Advanced Analytics**: Trend analysis and predictive maintenance alerts
- **Enhanced Graphs**: Visual representation of performance metrics over time

## Support & Contributing

### Bug Reports

Since this is a beta release, your feedback is valuable! Please report:
- Any bugs or unexpected behavior
- Drives that are not properly detected or supported
- Feature requests or suggestions