#!/bin/bash

# Interactive script to generate docker-compose.yml with dynamic device discovery
# Usage: ./generate-compose.sh

OUTPUT_FILE="docker-compose.yml"
BACKUP_FILE="docker-compose.yml.backup"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to generate a compatible secret
generate_secret() {
    # Generate URL-safe base64 secret (no problematic characters)
    local random_bytes=$(openssl rand -base64 32 2>/dev/null || head -c 32 /dev/urandom | base64)
    # Make it URL-safe by replacing problematic characters
    echo "$random_bytes" | tr '+/' '-_' | tr -d '='
}

# Function to ask yes/no questions
ask_yes_no() {
    local prompt="$1"
    local default="$2"
    local response

    while true; do
        if [ "$default" = "y" ]; then
            read -p "$prompt [Y/n]: " response
            response=${response:-y}
        else
            read -p "$prompt [y/N]: " response
            response=${response:-n}
        fi

        case $response in
            [Yy]* ) return 0;;
            [Nn]* ) return 1;;
            * ) echo "Please answer yes or no.";;
        esac
    done
}

# Function to discover block devices
discover_block_devices() {
    echo "      # Dynamically discovered block devices ($(date))"
    local count=0
    lsblk -d -n -o NAME,SIZE | grep '^sd' | while read device size; do
        echo "      - \"/dev/$device:/dev/$device\"  # $size"
        count=$((count + 1))
    done
    if [ $count -eq 0 ]; then
        echo "      # No block devices found ($(date))"
    fi
}

# Function to discover serial devices
discover_serial_devices() {
    local found=false

    # Check for ACM devices
    for device in /dev/ttyACM*; do
        if [ -e "$device" ]; then
            if [ "$found" = false ]; then
                echo "      # Dynamically discovered serial devices ($(date))"
                found=true
            fi
            echo "      - \"$device:$device\""
        fi
    done

    # Check for USB devices
    for device in /dev/ttyUSB*; do
        if [ -e "$device" ]; then
            if [ "$found" = false ]; then
                echo "      # Dynamically discovered serial devices ($(date))"
                found=true
            fi
            echo "      - \"$device:$device\""
        fi
    done

    if [ "$found" = false ]; then
        echo "      # No serial devices found ($(date))"
    fi
}

echo -e "${BLUE}=== Hako Foundry Docker Compose Generator ===${NC}"
echo ""

# Backup existing file if it exists
if [ -f "$OUTPUT_FILE" ]; then
    cp "$OUTPUT_FILE" "$BACKUP_FILE"
    echo -e "${YELLOW}Backed up existing $OUTPUT_FILE to $BACKUP_FILE${NC}"
    echo ""
fi

# 1. Generate random secret
echo -e "${GREEN}1. Generating secure secret...${NC}"
SECRET=$(generate_secret)
echo "Generated secret: $SECRET"
echo ""

# 2. Ask about storage type
echo -e "${GREEN}2. Storage Configuration${NC}"
echo "Choose storage type for configuration data:"
echo "  - Docker Volume: Managed by Docker, automatic cleanup, portable"
echo "  - Bind Mount: Direct host path, easier backup/access, persistent"
echo ""

STORAGE_TYPE=""
STORAGE_VALUE=""

if ask_yes_no "Use Docker volume instead of bind mount?" "n"; then
    STORAGE_TYPE="volume"
    read -p "Enter volume name [hako_config]: " STORAGE_VALUE
    STORAGE_VALUE=${STORAGE_VALUE:-hako_config}
    echo "Will use Docker volume: $STORAGE_VALUE"
else
    STORAGE_TYPE="bind"
    CURRENT_DIR=$(pwd)
    read -p "Enter bind mount path [$CURRENT_DIR]: " STORAGE_VALUE
    STORAGE_VALUE=${STORAGE_VALUE:-$CURRENT_DIR}
    echo "Will use bind mount: $STORAGE_VALUE"
fi
echo ""

# 3. Ask for port
echo -e "${GREEN}3. Network Configuration${NC}"
read -p "Enter host port [8080]: " HOST_PORT
HOST_PORT=${HOST_PORT:-8080}
echo "Will expose on port: $HOST_PORT"
echo ""

# 4. Ask about user/group configuration
echo -e "${GREEN}4. User/Group Configuration${NC}"
echo "Configure user and group IDs for file permissions:"
echo "  - Set PUID/PGID: Run container with specific user/group (recommended for file access)"
echo "  - Skip: Use container defaults (simpler but may cause permission issues)"
echo ""

USE_USER_CONFIG="false"
PUID=""
PGID=""

if ask_yes_no "Configure user and group IDs (PUID/PGID)?" "y"; then
    USE_USER_CONFIG="true"
    echo ""
    echo "Current user ID: $(id -u)"
    echo "Current group ID: $(id -g)"
    echo ""

    read -p "Enter PUID [$(id -u)]: " PUID
    PUID=${PUID:-$(id -u)}

    read -p "Enter PGID [$(id -g)]: " PGID
    PGID=${PGID:-$(id -g)}

    echo "Will use PUID=$PUID, PGID=$PGID"
else
    echo "Will use container default user/group"
fi
echo ""

# 5. Ask about open access
echo -e "${GREEN}5. Security Configuration${NC}"
echo "Open Access allows unrestricted access to the web interface."
echo "  - true: No authentication required (convenient but less secure)"
echo "  - false: Authentication required (more secure)"
echo ""

OPEN_ACCESS="false"
if ask_yes_no "Enable open access (no authentication)?" "n"; then
    OPEN_ACCESS="true"
fi
echo "Open access: $OPEN_ACCESS"
echo ""

# 6. Ask about auto-scanning drives
echo -e "${GREEN}6. Device Configuration${NC}"
echo "Auto-scan will automatically detect and add all available storage devices."
echo "This includes all /dev/sd* devices and serial ports (/dev/ttyACM*, /dev/ttyUSB*)."
echo ""

AUTOSCAN="false"
if ask_yes_no "Auto-scan for storage devices and serial ports?" "y"; then
    AUTOSCAN="true"
    echo ""
    echo -e "${YELLOW}Scanning for devices...${NC}"

    # Show what we found
    BLOCK_COUNT=$(lsblk -d -n -o NAME | grep '^sd' | wc -l)
    SERIAL_COUNT=0
    for device in /dev/ttyACM* /dev/ttyUSB*; do
        if [ -e "$device" ]; then
            SERIAL_COUNT=$((SERIAL_COUNT + 1))
        fi
    done

    echo "Found $BLOCK_COUNT block devices and $SERIAL_COUNT serial devices"

    if [ $BLOCK_COUNT -gt 0 ]; then
        echo "Block devices:"
        lsblk -d -n -o NAME,SIZE | grep '^sd' | head -5 | while read device size; do
            echo "  - /dev/$device ($size)"
        done
        if [ $BLOCK_COUNT -gt 5 ]; then
            echo "  ... and $((BLOCK_COUNT - 5)) more"
        fi
    fi

    if [ $SERIAL_COUNT -gt 0 ]; then
        echo "Serial devices:"
        for device in /dev/ttyACM* /dev/ttyUSB*; do
            if [ -e "$device" ]; then
                echo "  - $device"
            fi
        done
    fi
fi
echo ""

echo -e "${GREEN}7. Generating docker-compose.yml...${NC}"

# Generate the compose file header
cat > "$OUTPUT_FILE" << EOF
version: '3.8'

services:
  hako-foundry:
    image: hakoforge/hako-foundry
    container_name: hako-foundry
    pull_policy: always
    restart: unless-stopped

    # Port mapping
    ports:
      - "$HOST_PORT:8080"

    # Environment variables
    environment:
      - OPEN_ACCESS=$OPEN_ACCESS
      - SECRET=$SECRET
EOF

# Add PUID/PGID only if configured
if [ "$USE_USER_CONFIG" = "true" ]; then
    cat >> "$OUTPUT_FILE" << EOF
      - PUID=$PUID
      - PGID=$PGID
EOF
fi

cat >> "$OUTPUT_FILE" << EOF

    # Volumes
    volumes:
EOF

# Add storage configuration
if [ "$STORAGE_TYPE" = "volume" ]; then
    echo "      - $STORAGE_VALUE:/app/config/" >> "$OUTPUT_FILE"
else
    echo "      - $STORAGE_VALUE:/app/config/" >> "$OUTPUT_FILE"
fi

cat >> "$OUTPUT_FILE" << EOF
      - /sys/class/thermal:/sys/class/thermal:ro
      - /sys/class/hwmon:/sys/class/hwmon:ro

    # Capabilities
    cap_add:
      - SYS_RAWIO
EOF

# Add devices section if autoscan is enabled
if [ "$AUTOSCAN" = "true" ]; then
    echo "" >> "$OUTPUT_FILE"
    echo "    # Device mapping" >> "$OUTPUT_FILE"
    echo "    devices:" >> "$OUTPUT_FILE"
    discover_serial_devices >> "$OUTPUT_FILE"
    discover_block_devices >> "$OUTPUT_FILE"
else
    echo "" >> "$OUTPUT_FILE"
    echo "    # Device mapping (disabled - run with autoscan to populate)" >> "$OUTPUT_FILE"
    echo "    # devices:" >> "$OUTPUT_FILE"
    echo "    #   - \"/dev/sda:/dev/sda\"  # Add devices manually as needed" >> "$OUTPUT_FILE"
fi

# Add volumes section if using Docker volume
if [ "$STORAGE_TYPE" = "volume" ]; then
    cat >> "$OUTPUT_FILE" << EOF

# Named volumes
volumes:
  $STORAGE_VALUE:
    driver: local
EOF
else
    cat >> "$OUTPUT_FILE" << EOF

# No named volumes needed (using bind mount)
EOF
fi

echo -e "${GREEN}✓ Generated $OUTPUT_FILE successfully!${NC}"
echo ""
echo -e "${BLUE}Configuration Summary:${NC}"
echo "  Secret: $SECRET"
echo "  Storage: $STORAGE_TYPE ($STORAGE_VALUE)"
echo "  Port: $HOST_PORT"
if [ "$USE_USER_CONFIG" = "true" ]; then
    echo "  User/Group: PUID=$PUID, PGID=$PGID"
else
    echo "  User/Group: Container defaults"
fi
echo "  Open Access: $OPEN_ACCESS"
echo "  Device Auto-scan: $AUTOSCAN"
if [ "$AUTOSCAN" = "true" ]; then
    echo "  Devices Found: $BLOCK_COUNT block + $SERIAL_COUNT serial"
fi
echo ""
# Get server IP for final instructions
get_server_ip() {
    # Try to get the main IP address (not localhost)
    local ip=$(ip route get 1.1.1.1 2>/dev/null | grep -oP 'src \K\S+' || hostname -I | awk '{print $1}' || echo "localhost")
    echo "$ip"
}

SERVER_IP=$(get_server_ip)

echo -e "${YELLOW}Next steps:${NC}"
echo "1. Review the generated docker-compose.yml file"
if [ "$STORAGE_TYPE" = "bind" ]; then
    echo "2. Ensure the directory $STORAGE_VALUE exists and has proper permissions"
    echo -e "3. Run: ${GREEN}docker compose up -d${NC}"
    echo -e "4. Access at: ${BLUE}http://$SERVER_IP:$HOST_PORT${NC}"
else
    echo -e "2. Run: ${GREEN}docker compose up -d${NC}"
    echo -e "3. Access at: ${BLUE}http://$SERVER_IP:$HOST_PORT${NC}"
fi
echo ""
echo -e "${YELLOW}To regenerate with different settings, run this script again.${NC}"