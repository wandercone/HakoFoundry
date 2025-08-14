"""
Temperature Sensor Backend Library

This module provides backend functionality for managing temperature sensors and their data.
It can be reused across different pages that need temperature monitoring functionality.
"""

import json
import os
import time
import glob
import re
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

# Set up logging
logger = logging.getLogger("foundry_logger")

# No mock data - only real Linux hardware sensors will be used


class LinuxHardwareMonitor:
    """Handles reading temperature data from Linux hardware monitoring interfaces."""
    
    def __init__(self):
        """Initialize the Linux hardware monitor."""
        self.hwmon_path = "/sys/class/hwmon"
        self.thermal_path = "/sys/class/thermal"
        self.sensor_cache = {}
        self.last_scan = 0
        self.scan_interval = 30  # Rescan hardware every 30 seconds
    
    def _read_file_safe(self, file_path: str) -> Optional[str]:
        """Safely read a file and return its content."""
        try:
            with open(file_path, 'r') as f:
                return f.read().strip()
        except (OSError, IOError, PermissionError):
            return None
    
    def _get_sensor_name(self, hwmon_dir: str, temp_input: str) -> str:
        """Get a human-readable name for a temperature sensor."""
        # Extract sensor number from temp input file
        match = re.search(r'temp(\d+)_input', temp_input)
        sensor_num = match.group(1) if match else "unknown"
        
        # Try to get sensor label
        label_file = os.path.join(hwmon_dir, f"temp{sensor_num}_label")
        label = self._read_file_safe(label_file)
        if label:
            return label
        
        # Try to get device name
        name_file = os.path.join(hwmon_dir, "name")
        device_name = self._read_file_safe(name_file)
        if device_name:
            return f"{device_name} Temp {sensor_num}"
        
        # Fallback to generic name
        return f"Temperature Sensor {sensor_num}"
    
    def _scan_hwmon_sensors(self) -> Dict[str, str]:
        """Scan /sys/class/hwmon for temperature sensors."""
        sensors = {}
        
        if not os.path.exists(self.hwmon_path):
            return sensors
        
        try:
            for hwmon_device in os.listdir(self.hwmon_path):
                hwmon_dir = os.path.join(self.hwmon_path, hwmon_device)
                if not os.path.isdir(hwmon_dir):
                    continue
                
                # Look for temperature input files
                temp_files = glob.glob(os.path.join(hwmon_dir, "temp*_input"))
                for temp_file in temp_files:
                    sensor_name = self._get_sensor_name(hwmon_dir, os.path.basename(temp_file))
                    sensors[sensor_name] = temp_file
        except (OSError, PermissionError):
            pass
        
        return sensors
    
    def _scan_thermal_sensors(self) -> Dict[str, str]:
        """Scan /sys/class/thermal for thermal zone sensors."""
        sensors = {}
        
        if not os.path.exists(self.thermal_path):
            return sensors
        
        try:
            thermal_zones = glob.glob(os.path.join(self.thermal_path, "thermal_zone*"))
            for zone_path in thermal_zones:
                if not os.path.isdir(zone_path):
                    continue
                
                # Get zone type (if available)
                type_file = os.path.join(zone_path, "type")
                zone_type = self._read_file_safe(type_file)
                
                # Get zone number
                zone_num = os.path.basename(zone_path).replace("thermal_zone", "")
                
                # Create sensor name
                if zone_type:
                    sensor_name = f"{zone_type} (Zone {zone_num})"
                else:
                    sensor_name = f"Thermal Zone {zone_num}"
                
                temp_file = os.path.join(zone_path, "temp")
                if os.path.exists(temp_file):
                    sensors[sensor_name] = temp_file
        except (OSError, PermissionError):
            pass
        
        return sensors
    
    def scan_available_sensors(self) -> Dict[str, str]:
        """Scan for all available temperature sensors on the system."""
        current_time = time.time()
        
        # Use cache if recent scan
        if (current_time - self.last_scan) < self.scan_interval and self.sensor_cache:
            return self.sensor_cache.copy()
        
        # Scan both hwmon and thermal sensors
        sensors = {}
        sensors.update(self._scan_hwmon_sensors())
        sensors.update(self._scan_thermal_sensors())
        
        # Update cache
        self.sensor_cache = sensors
        self.last_scan = current_time
        
        return sensors.copy()
    
    def read_temperature(self, sensor_path: str) -> Optional[float]:
        """Read temperature from a sensor file path."""
        temp_str = self._read_file_safe(sensor_path)
        if temp_str is None:
            return None
        
        try:
            # Convert from millidegrees to degrees Celsius
            temp_millidegrees = int(temp_str)
            temp_celsius = temp_millidegrees / 1000.0
            return round(temp_celsius, 1)
        except ValueError:
            return None
    
    def get_sensor_info(self, sensor_path: str) -> Dict[str, Any]:
        """Get detailed information about a sensor."""
        info = {
            "path": sensor_path,
            "temperature": self.read_temperature(sensor_path),
            "available": os.path.exists(sensor_path) if sensor_path else False
        }
        
        # Try to get additional sensor info from hwmon
        if "/hwmon/" in sensor_path:
            hwmon_dir = os.path.dirname(sensor_path)
            sensor_num = re.search(r'temp(\d+)_input', sensor_path)
            
            if sensor_num:
                num = sensor_num.group(1)
                
                # Try to get min/max values
                min_file = os.path.join(hwmon_dir, f"temp{num}_min")
                max_file = os.path.join(hwmon_dir, f"temp{num}_max")
                crit_file = os.path.join(hwmon_dir, f"temp{num}_crit")
                
                min_temp = self._read_file_safe(min_file)
                max_temp = self._read_file_safe(max_file)
                crit_temp = self._read_file_safe(crit_file)
                
                if min_temp:
                    try:
                        info["min_temp"] = int(min_temp) / 1000.0
                    except ValueError:
                        pass
                
                if max_temp:
                    try:
                        info["max_temp"] = int(max_temp) / 1000.0
                    except ValueError:
                        pass
                
                if crit_temp:
                    try:
                        info["critical_temp"] = int(crit_temp) / 1000.0
                    except ValueError:
                        pass
        
        return info


class TemperatureSensor:
    """Represents a single temperature sensor with name and current temperature."""
    
    def __init__(self, name: str, temperature: float = 0.0, enabled: bool = True, hardware_path: str = None):
        """
        Initialize a temperature sensor.
        
        Args:
            name: Display name of the sensor
            temperature: Current temperature reading in Celsius
            enabled: Whether the sensor is active/enabled
            hardware_path: Path to the hardware sensor file (for Linux hwmon/thermal)
        """
        self.name = name
        self.temperature = temperature
        self.enabled = enabled
        self.hardware_path = hardware_path
        self.last_updated = datetime.now()
        self.history: List[Tuple[datetime, float]] = []
        self.min_temp = temperature
        self.max_temp = temperature
        self.hardware_monitor = LinuxHardwareMonitor()
        
    def update_temperature(self, temperature: float = None) -> None:
        """Update the sensor temperature and maintain history."""
        # If no temperature provided, try to read from hardware
        if temperature is None:
            temperature = self.read_hardware_temperature()
        
        if temperature is not None:
            self.temperature = temperature
            self.last_updated = datetime.now()
            
            # Update min/max tracking
            if temperature < self.min_temp:
                self.min_temp = temperature
            if temperature > self.max_temp:
                self.max_temp = temperature
                
            # Add to history (keep last 100 readings)
            self.history.append((self.last_updated, temperature))
            if len(self.history) > 100:
                self.history.pop(0)
    
    def read_hardware_temperature(self) -> Optional[float]:
        """Read temperature from hardware sensor if available."""
        if self.hardware_path and os.path.exists(self.hardware_path):
            return self.hardware_monitor.read_temperature(self.hardware_path)
        return None
    
    # Mock temperature generation removed - only real hardware sensors supported
    
    def get_current_temperature(self) -> float:
        """Get current temperature from hardware sensor only."""
        if self.enabled:
            # Try to read from hardware
            hw_temp = self.read_hardware_temperature()
            if hw_temp is not None:
                return hw_temp
            
            # If no hardware reading available, return cached temperature or 0
            return self.temperature if self.temperature > 0 else 0.0
        return 0.0
    
    def is_hardware_available(self) -> bool:
        """Check if hardware sensor is available."""
        return self.hardware_path is not None and os.path.exists(self.hardware_path)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert sensor to dictionary representation."""
        return {
            "name": self.name,
            "temperature": self.temperature,
            "enabled": self.enabled,
            "hardware_path": self.hardware_path,
            "hardware_available": self.is_hardware_available(),
            "last_updated": self.last_updated.isoformat(),
            "min_temp": self.min_temp,
            "max_temp": self.max_temp
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'TemperatureSensor':
        """Create sensor from dictionary representation."""
        sensor = cls(
            name=data["name"],
            temperature=data["temperature"],
            enabled=data.get("enabled", True),
            hardware_path=data.get("hardware_path")
        )
        sensor.min_temp = data.get("min_temp", sensor.temperature)
        sensor.max_temp = data.get("max_temp", sensor.temperature)
        
        if "last_updated" in data:
            try:
                sensor.last_updated = datetime.fromisoformat(data["last_updated"])
            except ValueError:
                sensor.last_updated = datetime.now()
                
        return sensor


class SensorGroup:
    """Represents a group of related temperature sensors."""
    
    def __init__(self, name: str, sensors: Optional[List[TemperatureSensor]] = None):
        """
        Initialize a sensor group.
        
        Args:
            name: Name of the sensor group (e.g., "CPU", "GPU", "Storage")
            sensors: List of temperature sensors in this group
        """
        self.name = name
        self.sensors: Dict[str, TemperatureSensor] = {}
        self.enabled = True
        
        if sensors:
            for sensor in sensors:
                self.sensors[sensor.name] = sensor
    
    def add_sensor(self, sensor: TemperatureSensor) -> None:
        """Add a sensor to this group."""
        self.sensors[sensor.name] = sensor
    
    def remove_sensor(self, sensor_name: str) -> bool:
        """Remove a sensor from this group."""
        if sensor_name in self.sensors:
            del self.sensors[sensor_name]
            return True
        return False
    
    def get_sensor(self, sensor_name: str) -> Optional[TemperatureSensor]:
        """Get a specific sensor by name."""
        return self.sensors.get(sensor_name)
    
    def get_average_temperature(self) -> float:
        """Calculate average temperature of enabled sensors in this group."""
        enabled_sensors = [s for s in self.sensors.values() if s.enabled]
        if not enabled_sensors:
            return 0.0
        
        total_temp = sum(s.get_current_temperature() for s in enabled_sensors)
        return round(total_temp / len(enabled_sensors), 1)
    
    def get_max_temperature(self) -> float:
        """Get maximum temperature from enabled sensors in this group."""
        enabled_sensors = [s for s in self.sensors.values() if s.enabled]
        if not enabled_sensors:
            return 0.0
        return max(s.get_current_temperature() for s in enabled_sensors)
    
    def update_all_sensors(self) -> None:
        """Update all sensors in this group with real hardware data only."""
        for sensor in self.sensors.values():
            if sensor.enabled:
                # Only update from hardware - no mock data fallback
                hw_temp = sensor.read_hardware_temperature()
                if hw_temp is not None:
                    sensor.update_temperature(hw_temp)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert group to dictionary representation."""
        return {
            "name": self.name,
            "enabled": self.enabled,
            "sensors": {name: sensor.to_dict() for name, sensor in self.sensors.items()}
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'SensorGroup':
        """Create sensor group from dictionary representation."""
        group = cls(data["name"])
        group.enabled = data.get("enabled", True)
        
        for sensor_name, sensor_data in data.get("sensors", {}).items():
            sensor = TemperatureSensor.from_dict(sensor_data)
            group.add_sensor(sensor)
            
        return group


class TemperatureConfigManager:
    """Manages persistence of temperature sensor configurations."""
    
    def __init__(self, config_file: str = "config/temperature_sensors_config.json"):
        """
        Initialize the config manager.
        
        Args:
            config_file: Path to the configuration file
        """
        self.config_file = config_file
        self.ensure_config_directory()
    
    def ensure_config_directory(self) -> None:
        """Ensure the config directory exists."""
        config_dir = os.path.dirname(self.config_file)
        if config_dir and not os.path.exists(config_dir):
            os.makedirs(config_dir, exist_ok=True)
    
    def save_config(self, sensor_groups: Dict[str, SensorGroup], drive_monitors: Dict[str, 'DriveTemperatureMonitor'] = None) -> bool:
        """
        Save sensor groups and drive monitors configuration to file.
        
        Args:
            sensor_groups: Dictionary of sensor groups to save
            drive_monitors: Dictionary of drive monitors to save
            
        Returns:
            True if successful, False otherwise
        """
        try:
            config_data = {
                "version": "1.0",
                "last_saved": datetime.now().isoformat(),
                "sensor_groups": {name: group.to_dict() for name, group in sensor_groups.items()},
                "drive_monitors": {name: monitor.to_dict() for name, monitor in (drive_monitors or {}).items()}
            }
            
            with open(self.config_file, 'w') as f:
                json.dump(config_data, f, indent=4)
            return True
        except Exception as e:
            logger.error(f"Error saving temperature sensor config: {e}")
            return False
    
    def load_config(self) -> Tuple[Dict[str, SensorGroup], Dict[str, 'DriveTemperatureMonitor']]:
        """
        Load sensor groups and drive monitors configuration from file.
        
        Returns:
            Tuple of (sensor_groups, drive_monitors) dictionaries, or defaults if load fails
        """
        try:
            if os.path.exists(self.config_file):
                with open(self.config_file, 'r') as f:
                    config_data = json.load(f)
                
                sensor_groups = {}
                for group_name, group_data in config_data.get("sensor_groups", {}).items():
                    sensor_groups[group_name] = SensorGroup.from_dict(group_data)
                
                drive_monitors = {}
                for key, monitor_data in config_data.get("drive_monitors", {}).items():
                    monitor = DriveTemperatureMonitor.from_dict(monitor_data)
                    
                    # Migration: if the key looks like a monitor name (not a curve ID), use the curve_id from the monitor
                    if monitor.curve_id and (len(key) > 36 or ' ' in key):  # Curve IDs are typically 36 chars UUID
                        # This looks like an old monitor name, use curve_id as key instead
                        drive_monitors[monitor.curve_id] = monitor
                        logger.info(f"Migrated drive monitor from name-based key '{key}' to curve-based key '{monitor.curve_id}'")
                    else:
                        # Already using curve_id as key, or no curve_id available
                        drive_monitors[key] = monitor
                
                return sensor_groups, drive_monitors
            else:
                return self.get_default_config(), {}
        except Exception as e:
            logger.error(f"Error loading temperature sensor config: {e}")
            return self.get_default_config(), {}
    
    def get_default_config(self) -> Dict[str, SensorGroup]:
        """Create default sensor groups configuration using only detected hardware sensors."""
        hardware_monitor = LinuxHardwareMonitor()
        available_hw_sensors = hardware_monitor.scan_available_sensors()
        
        # Initialize groups
        cpu_group = SensorGroup("CPU")
        gpu_group = SensorGroup("GPU") 
        storage_group = SensorGroup("Storage")
        system_group = SensorGroup("System")
        other_group = SensorGroup("Other")
        
        # Only process detected hardware sensors
        for sensor_name, sensor_path in available_hw_sensors.items():
            sensor = TemperatureSensor(sensor_name, enabled=True, hardware_path=sensor_path)
            # Read initial temperature
            initial_temp = sensor.read_hardware_temperature()
            if initial_temp is not None:
                sensor.update_temperature(initial_temp)
            
            # Categorize by sensor name patterns
            sensor_name_lower = sensor_name.lower()
            
            if any(keyword in sensor_name_lower for keyword in ['cpu', 'core', 'package', 'ccd', 'processor']):
                cpu_group.add_sensor(sensor)
            elif any(keyword in sensor_name_lower for keyword in ['gpu', 'graphics', 'video', 'radeon', 'nvidia', 'amd']):
                gpu_group.add_sensor(sensor)
            elif any(keyword in sensor_name_lower for keyword in ['nvme', 'ssd', 'hdd', 'drive', 'storage', 'disk']):
                storage_group.add_sensor(sensor)
            elif any(keyword in sensor_name_lower for keyword in ['acpi', 'thermal', 'zone', 'ambient', 'case', 'system', 'motherboard', 'chipset', 'vrm', 'psu', 'ram', 'memory']):
                system_group.add_sensor(sensor)
            else:
                other_group.add_sensor(sensor)
        
        # Build result, only include groups that have sensors
        result = {}
        for group_name, group in [("CPU", cpu_group), ("GPU", gpu_group), ("Storage", storage_group), ("System", system_group), ("Other", other_group)]:
            if group.sensors:  # Only add groups that have sensors
                result[group_name] = group
        
        # If no hardware sensors found, return empty config
        if not result:
            logger.warning("No hardware temperature sensors detected on this system")
        
        return result


class SensorManagementService:
    """Main backend class for temperature sensor management."""
    
    def __init__(self, config_file: str = "config/temperature_sensors_config.json"):
        """
        Initialize the temperature sensor backend.
        
        Args:
            config_file: Path to the configuration file
        """
        self.config_manager = TemperatureConfigManager(config_file)
        self.hardware_monitor = LinuxHardwareMonitor()
        self.sensor_groups: Dict[str, SensorGroup] = {}
        self.drive_monitors: Dict[str, DriveTemperatureMonitor] = {}  # Add drive monitors
        self.last_update = datetime.now()
        self.auto_update_interval = 5.0  # seconds
        
        # Load existing configuration or create default
        self.load_configuration()
    
    def load_configuration(self) -> None:
        """Load sensor configuration and drive monitors from file."""
        # Check if config file exists before loading
        config_exists = os.path.exists(self.config_manager.config_file)
        
        self.sensor_groups, self.drive_monitors = self.config_manager.load_config()
        self.last_update = datetime.now()
        
        # If config file didn't exist, save the default configuration for future use
        if not config_exists:
            try:
                self.save_configuration()
                logger.info("Default temperature sensor configuration saved to config file")
            except Exception as e:
                logger.error(f"Failed to save default temperature sensor configuration: {e}")
    
    def save_configuration(self) -> bool:
        """Save current sensor configuration and drive monitors to file."""
        return self.config_manager.save_config(self.sensor_groups, self.drive_monitors)
    
    def get_sensor_groups(self) -> Dict[str, SensorGroup]:
        """Get all sensor groups."""
        return self.sensor_groups.copy()
    
    def get_sensor_group(self, group_name: str) -> Optional[SensorGroup]:
        """Get a specific sensor group by name."""
        return self.sensor_groups.get(group_name)
    
    def add_sensor_group(self, group: SensorGroup) -> None:
        """Add a new sensor group."""
        self.sensor_groups[group.name] = group
    
    def remove_sensor_group(self, group_name: str) -> bool:
        """Remove a sensor group."""
        if group_name in self.sensor_groups:
            del self.sensor_groups[group_name]
            return True
        return False
    
    def get_sensor(self, group_name: str, sensor_name: str) -> Optional[TemperatureSensor]:
        """Get a specific sensor by group and sensor name."""
        group = self.get_sensor_group(group_name)
        if group:
            return group.get_sensor(sensor_name)
        return None
    
    def add_sensor_to_group(self, group_name: str, sensor: TemperatureSensor) -> bool:
        """Add a sensor to a specific group."""
        group = self.get_sensor_group(group_name)
        if group:
            group.add_sensor(sensor)
            return True
        return False
    
    def remove_sensor_from_group(self, group_name: str, sensor_name: str) -> bool:
        """Remove a sensor from a specific group."""
        group = self.get_sensor_group(group_name)
        if group:
            return group.remove_sensor(sensor_name)
        return False
    
    def update_all_sensors(self) -> None:
        """Update all sensors with real hardware temperature data."""
        for group in self.sensor_groups.values():
            if group.enabled:
                group.update_all_sensors()
        
        # Also update drive monitors
        for monitor in self.drive_monitors.values():
            if monitor.enabled:
                monitor.update_temperature()
        
        self.last_update = datetime.now()
    
    def get_all_sensors_flat(self) -> Dict[str, TemperatureSensor]:
        """Get all sensors in a flat dictionary (group_name.sensor_name -> sensor)."""
        all_sensors = {}
        for group_name, group in self.sensor_groups.items():
            for sensor_name, sensor in group.sensors.items():
                key = f"{group_name}.{sensor_name}"
                all_sensors[key] = sensor
        return all_sensors
    
    def get_sensors_by_name(self, sensor_names: List[str]) -> List[TemperatureSensor]:
        """Get sensors by their display names from any group."""
        found_sensors = []
        for group in self.sensor_groups.values():
            for sensor_name, sensor in group.sensors.items():
                if sensor_name in sensor_names:
                    found_sensors.append(sensor)
        return found_sensors
    
    def get_available_sensor_names(self) -> List[str]:
        """Get list of all available hardware sensor names."""
        # Only return detected hardware sensors
        hw_sensors = list(self.hardware_monitor.scan_available_sensors().keys())
        return hw_sensors
    
    def scan_hardware_sensors(self) -> Dict[str, str]:
        """Scan for available hardware temperature sensors."""
        return self.hardware_monitor.scan_available_sensors()
    
    def create_sensor_from_available(self, sensor_name: str) -> Optional[TemperatureSensor]:
        """Create a new sensor instance from available hardware sensor names only."""
        # Only create sensors for detected hardware
        hw_sensors = self.hardware_monitor.scan_available_sensors()
        if sensor_name in hw_sensors:
            sensor = TemperatureSensor(sensor_name, enabled=True, hardware_path=hw_sensors[sensor_name])
            initial_temp = sensor.read_hardware_temperature()
            if initial_temp is not None:
                sensor.update_temperature(initial_temp)
            return sensor
        
        return None
    
    def refresh_hardware_sensors(self) -> int:
        """Scan for new hardware sensors and add them to appropriate groups."""
        hw_sensors = self.hardware_monitor.scan_available_sensors()
        added_count = 0
        
        # Check if we need to add new sensors
        existing_hw_paths = set()
        for group in self.sensor_groups.values():
            for sensor in group.sensors.values():
                if sensor.hardware_path:
                    existing_hw_paths.add(sensor.hardware_path)
        
        # Add new hardware sensors
        for sensor_name, sensor_path in hw_sensors.items():
            if sensor_path not in existing_hw_paths:
                sensor = TemperatureSensor(sensor_name, enabled=True, hardware_path=sensor_path)
                initial_temp = sensor.read_hardware_temperature()
                if initial_temp is not None:
                    sensor.update_temperature(initial_temp)
                
                # Categorize and add to appropriate group
                sensor_name_lower = sensor_name.lower()
                target_group = "Other"  # Default
                
                if any(keyword in sensor_name_lower for keyword in ['cpu', 'core', 'package', 'ccd', 'processor']):
                    target_group = "CPU"
                elif any(keyword in sensor_name_lower for keyword in ['gpu', 'graphics', 'video', 'radeon', 'nvidia', 'amd']):
                    target_group = "GPU"
                elif any(keyword in sensor_name_lower for keyword in ['nvme', 'ssd', 'hdd', 'drive', 'storage', 'disk']):
                    target_group = "Storage"
                elif any(keyword in sensor_name_lower for keyword in ['acpi', 'thermal', 'zone', 'ambient', 'case', 'system', 'motherboard', 'chipset', 'vrm', 'psu', 'ram', 'memory']):
                    target_group = "System"
                
                # Create group if it doesn't exist
                if target_group not in self.sensor_groups:
                    self.sensor_groups[target_group] = SensorGroup(target_group)
                
                self.sensor_groups[target_group].add_sensor(sensor)
                added_count += 1
        
        return added_count
    
    def add_drive_monitor(self, monitor: 'DriveTemperatureMonitor') -> None:
        """Add a drive temperature monitor using curve ID as key."""
        if monitor.curve_id:
            self.drive_monitors[monitor.curve_id] = monitor
            self.save_configuration()  # Auto-save when drive monitor is added
        else:
            logger.warning("Cannot add drive monitor without curve_id")
    
    def remove_drive_monitor(self, curve_id: str) -> bool:
        """Remove a drive temperature monitor by curve ID."""
        if curve_id in self.drive_monitors:
            del self.drive_monitors[curve_id]
            self.save_configuration()  # Auto-save when drive monitor is removed
            return True
        return False
    
    def get_drive_monitor(self, curve_id: str) -> Optional['DriveTemperatureMonitor']:
        """Get a drive temperature monitor by curve ID."""
        return self.drive_monitors.get(curve_id)
    
    def get_all_drive_monitors(self) -> Dict[str, 'DriveTemperatureMonitor']:
        """Get all drive temperature monitors."""
        return self.drive_monitors.copy()
    
    def update_drive_monitors(self) -> None:
        """Update all drive temperature monitors."""
        for monitor in self.drive_monitors.values():
            if monitor.enabled:
                monitor.update_temperature()
    
    def get_drive_monitors_for_curve(self, curve_id: str) -> Dict[str, 'DriveTemperatureMonitor']:
        """Get drive monitor for a specific curve ID."""
        if curve_id in self.drive_monitors:
            return {curve_id: self.drive_monitors[curve_id]}
        return {}
    
    def remove_drive_monitors_for_curve(self, curve_id: str) -> int:
        """Remove drive monitor for a specific curve ID. Returns count of removed monitors."""
        if curve_id in self.drive_monitors:
            del self.drive_monitors[curve_id]
            self.save_configuration()  # Auto-save when drive monitor is removed
            return 1
        return 0
    
    def has_drive_monitor_for_curve(self, curve_id: str) -> bool:
        """Check if a curve already has a drive monitor."""
        return curve_id in self.drive_monitors
    
    def get_combined_temperature_sources(self) -> List[str]:
        """Get all available temperature sources (sensors + drive monitors)."""
        sources = []
        
        # Add individual sensors
        for group_name, group in self.sensor_groups.items():
            for sensor_name, sensor in group.sensors.items():
                if sensor.enabled and sensor.is_hardware_available():
                    sources.append(f"{group_name}.{sensor_name}")
        
        # Add drive monitors
        for curve_id, monitor in self.drive_monitors.items():
            if monitor.enabled and monitor.is_hardware_available():
                sources.append(f"Drives.{monitor.name}")
        
        return sources
    
    def get_temperature_by_source_name(self, source_name: str) -> Optional[float]:
        """Get temperature reading by source name (supports both sensors and drive monitors)."""
        if source_name.startswith("Drives."):
            # Drive monitor - need to find by monitor name
            monitor_name = source_name[7:]  # Remove "Drives." prefix
            for curve_id, monitor in self.drive_monitors.items():
                if monitor.name == monitor_name:
                    return monitor.get_current_temperature()
        else:
            # Regular sensor (group.sensor format)
            parts = source_name.split(".", 1)
            if len(parts) == 2:
                group_name, sensor_name = parts
                sensor = self.get_sensor(group_name, sensor_name)
                if sensor:
                    return sensor.get_current_temperature()
        
        return None
    
    def get_summary_stats(self) -> Dict[str, Any]:
        """Get summary statistics for all sensors."""
        total_sensors = 0
        enabled_sensors = 0
        hardware_sensors = 0
        temperatures = []
        
        for group in self.sensor_groups.values():
            total_sensors += len(group.sensors)
            for sensor in group.sensors.values():
                if sensor.enabled:
                    enabled_sensors += 1
                    current_temp = sensor.get_current_temperature()
                    temperatures.append(current_temp)
                    
                if sensor.is_hardware_available():
                    hardware_sensors += 1
        
        stats = {
            "total_sensors": total_sensors,
            "enabled_sensors": enabled_sensors,
            "hardware_sensors": hardware_sensors,
            "mock_sensors": total_sensors - hardware_sensors,
            "average_temperature": round(sum(temperatures) / len(temperatures), 1) if temperatures else 0.0,
            "max_temperature": max(temperatures) if temperatures else 0.0,
            "min_temperature": min(temperatures) if temperatures else 0.0,
            "last_update": self.last_update.isoformat()
        }
        
        return stats


class DriveTemperatureMonitor:
    """
    Monitors temperatures from selected hard drives and provides average/maximum calculations.
    Integrates with the global drive manager to get actual drive temperature data.
    """
    
    def __init__(self, name: str = "Drive Temperature Monitor", aggregation_mode: str = "average", curve_id: str = None):
        """
        Initialize the drive temperature monitor.
        
        Args:
            name: Display name for this monitor
            aggregation_mode: How to calculate temperature from multiple drives ("average" or "maximum")
            curve_id: ID of the fan curve this monitor is associated with
        """
        self.name = name
        self.aggregation_mode = aggregation_mode  # "average" or "maximum"
        self.curve_id = curve_id  # Fan curve ID this monitor belongs to
        self.selected_drive_hashes = set()  # Set of drive hashes to monitor
        self.enabled = True
        self.last_updated = datetime.now()
        self.current_temperature = 0.0
        self.min_temp = 0.0
        self.max_temp = 0.0
        self.history: List[Tuple[datetime, float]] = []
    
    def add_drive(self, drive_hash: str) -> None:
        """Add a drive to monitor by its hash."""
        self.selected_drive_hashes.add(drive_hash)
    
    def remove_drive(self, drive_hash: str) -> None:
        """Remove a drive from monitoring."""
        self.selected_drive_hashes.discard(drive_hash)
    
    def clear_drives(self) -> None:
        """Clear all selected drives."""
        self.selected_drive_hashes.clear()
    
    def set_drives(self, drive_hashes: List[str]) -> None:
        """Set the list of drives to monitor."""
        self.selected_drive_hashes = set(drive_hashes)
    
    def get_selected_drives(self) -> List[str]:
        """Get list of selected drive hashes."""
        return list(self.selected_drive_hashes)
    
    def set_aggregation_mode(self, mode: str) -> None:
        """Set the temperature aggregation mode."""
        if mode in ["average", "maximum"]:
            self.aggregation_mode = mode
    
    def get_curve_id(self) -> str:
        """Get the curve ID this monitor is associated with."""
        return self.curve_id
    
    def set_curve_id(self, curve_id: str) -> None:
        """Set the curve ID this monitor is associated with."""
        self.curve_id = curve_id
    
    def get_drive_temperatures(self) -> Dict[str, float]:
        """Get current temperatures from all selected drives."""
        import globals  # Import here to avoid circular dependency
        
        drive_temps = {}
        
        if globals.drivesList:
            for drive_hash in self.selected_drive_hashes:
                if drive_hash in globals.drivesList:
                    drive = globals.drivesList[drive_hash]
                    # Get temperature from drive object
                    temp = getattr(drive, 'temp', 0.0)
                    if isinstance(temp, (int, float)) and temp > 0:
                        drive_temps[drive_hash] = float(temp)
        
        return drive_temps
    
    def calculate_temperature(self) -> float:
        """Calculate temperature based on selected drives and aggregation mode."""
        drive_temps = self.get_drive_temperatures()
        
        if not drive_temps:
            return 0.0
        
        temperatures = list(drive_temps.values())
        
        if self.aggregation_mode == "maximum":
            return max(temperatures)
        else:  # default to average
            return round(sum(temperatures) / len(temperatures), 1)
    
    def update_temperature(self) -> None:
        """Update the current temperature reading."""
        new_temp = self.calculate_temperature()
        
        if new_temp > 0:
            self.current_temperature = new_temp
            self.last_updated = datetime.now()
            
            # Update min/max tracking
            if self.min_temp == 0.0 or new_temp < self.min_temp:
                self.min_temp = new_temp
            if new_temp > self.max_temp:
                self.max_temp = new_temp
            
            # Add to history (keep last 100 readings)
            self.history.append((self.last_updated, new_temp))
            if len(self.history) > 100:
                self.history.pop(0)
    
    def get_current_temperature(self) -> float:
        """Get current temperature (auto-updates if enabled)."""
        if self.enabled:
            self.update_temperature()
            return self.current_temperature
        return 0.0
    
    def get_drive_count(self) -> int:
        """Get number of selected drives."""
        return len(self.selected_drive_hashes)
    
    def get_available_drive_count(self) -> int:
        """Get number of selected drives that are actually available."""
        import globals
        
        if not globals.drivesList:
            return 0
        
        available_count = 0
        for drive_hash in self.selected_drive_hashes:
            if drive_hash in globals.drivesList:
                available_count += 1
        
        return available_count
    
    def is_hardware_available(self) -> bool:
        """Check if any selected drives are available for temperature reading."""
        return self.get_available_drive_count() > 0
    
    def get_status_summary(self) -> str:
        """Get a summary string describing the monitor status."""
        available = self.get_available_drive_count()
        total = self.get_drive_count()
        
        if total == 0:
            return "No drives selected"
        elif available == 0:
            return f"{total} drives selected (none available)"
        elif available == total:
            return f"{available} drives selected"
        else:
            return f"{available}/{total} drives available"
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert monitor to dictionary representation."""
        return {
            "name": self.name,
            "aggregation_mode": self.aggregation_mode,
            "curve_id": self.curve_id,
            "selected_drive_hashes": list(self.selected_drive_hashes),
            "enabled": self.enabled,
            "current_temperature": self.current_temperature,
            "min_temp": self.min_temp,
            "max_temp": self.max_temp,
            "last_updated": self.last_updated.isoformat(),
            "drive_count": self.get_drive_count(),
            "available_drive_count": self.get_available_drive_count()
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'DriveTemperatureMonitor':
        """Create monitor from dictionary representation."""
        monitor = cls(
            name=data.get("name", "Drive Temperature Monitor"),
            aggregation_mode=data.get("aggregation_mode", "average"),
            curve_id=data.get("curve_id")
        )
        
        monitor.selected_drive_hashes = set(data.get("selected_drive_hashes", []))
        monitor.enabled = data.get("enabled", True)
        monitor.current_temperature = data.get("current_temperature", 0.0)
        monitor.min_temp = data.get("min_temp", 0.0)
        monitor.max_temp = data.get("max_temp", 0.0)
        
        if "last_updated" in data:
            try:
                monitor.last_updated = datetime.fromisoformat(data["last_updated"])
            except ValueError:
                monitor.last_updated = datetime.now()
        
        return monitor


# Utility function to process temperature data for charts/visualization
def process_temperature_data(sensors: List[TemperatureSensor]) -> Dict[str, Any]:
    """
    Process temperature sensor data for visualization components.
    
    Args:
        sensors: List of temperature sensors
        
    Returns:
        Dictionary containing processed data for charts
    """
    if not sensors:
        return {"labels": [], "datasets": []}
    
    labels = [sensor.name for sensor in sensors]
    temperatures = [sensor.get_current_temperature() for sensor in sensors]
    
    # Create color mapping based on temperature ranges
    colors = []
    for temp in temperatures:
        if temp < 30:
            colors.append("#4ade80")  # Green - cool
        elif temp < 50:
            colors.append("#facc15")  # Yellow - warm
        elif temp < 70:
            colors.append("#f97316")  # Orange - hot
        else:
            colors.append("#ef4444")  # Red - very hot
    
    return {
        "labels": labels,
        "datasets": [{
            "label": "Temperature (°C)",
            "data": temperatures,
            "backgroundColor": colors,
            "borderColor": colors,
            "borderWidth": 1
        }]
    }
