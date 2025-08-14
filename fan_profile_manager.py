"""
Fan Control Backend Library

This module provides backend functionality for managing fan control profiles and curves.
It can be reused across different pages that need fan control functionality.
"""

import json
import os
import uuid
import logging
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any

# Default fan curve template
DEFAULT_FAN_CURVE_TEMPLATE = [
    {"x": 30, "y": 50},
    {"x": 40, "y": 60},
    {"x": 50, "y": 70},
    {"x": 60, "y": 80},
    {"x": 70, "y": 90},
    {"x": 80, "y": 100},
]

# Configure logging
logger = logging.getLogger("foundry_logger")


class FanCurve:
    """Represents a single fan curve with temperature-speed data points."""
    
    def __init__(self, index: int = 1):
        self.id = str(uuid.uuid4())  # Generate unique ID for the curve
        self.name = f"Fan Curve {index}"
        self.sensor = None
        # Default curve data points
        self._data = DEFAULT_FAN_CURVE_TEMPLATE.copy()

    def get_current_speed(self, backend: 'FanControlBackend' = None) -> Optional[float]:
        """
        Get the current fan speed percentage based on the assigned sensor's temperature.
        
        Args:
            backend: FanControlBackend instance to get sensor temperature readings
            
        Returns:
            Current fan speed percentage (0-100), or None if no sensor assigned or temperature unavailable
        """
        if not self.sensor or not backend:
            return None
        
        # Get current temperature from the assigned sensor
        current_temp = backend.get_sensor_temperature(self.sensor)
        if current_temp is None:
            return None
        
        # Use the existing interpolate_fan_speed function
        return interpolate_fan_speed(self._data, current_temp)

    def set_name(self, new_name: str) -> None:
        """Set a new name for the curve."""
        self.name = new_name

    def to_json(self) -> Dict[str, Any]:
        """Serialize curve to JSON format."""
        return {
            "id": self.id,
            "name": self.name,
            "sensor": self.sensor,
            "data": self._data
        }
    
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'FanCurve':
        """Create a FanCurve from JSON data."""
        curve = cls(1)  # Index doesn't matter for loading
        curve.id = data.get("id", str(uuid.uuid4()))  # Use existing ID or generate new one
        curve.name = data.get("name", "Fan Curve")
        curve.sensor = data.get("sensor", None)
        curve._data = data.get("data", DEFAULT_FAN_CURVE_TEMPLATE.copy())
        return curve


class FanControlProfile:
    """Represents a complete fan control profile with multiple curves."""
    
    def __init__(self, index: int = 1):
        self.id = str(uuid.uuid4())  # Generate unique ID for the profile
        # Initialize with 1 curve - use curve ID as dictionary key
        self._name = f'Fan Profile {index}'
        first_curve = FanCurve(1)
        self._fan_curves = {first_curve.id: first_curve}
        
    def get_name(self) -> str:
        """Get the profile name."""
        return self._name
    
    def set_name(self, name: str) -> None:
        """Set the profile name."""
        self._name = name

    def add_curve(self) -> str:
        """Add a new curve to the profile and return its ID."""
        next_available_id = 1
        while True:
            curve_name = f"Fan Curve {next_available_id}"
            # Check if this name already exists (we still want unique names for display)
            name_exists = any(curve.name == curve_name for curve in self._fan_curves.values())
            if not name_exists:
                new_curve = FanCurve(next_available_id)
                self._fan_curves[new_curve.id] = new_curve
                return new_curve.id
            next_available_id += 1

    def remove_curve(self, curve_id: str) -> bool:
        """Remove a curve from the profile by ID. Returns True if successful."""
        if len(self._fan_curves) <= 1:
            return False
        
        if curve_id in self._fan_curves:
            del self._fan_curves[curve_id]
            return True
        return False
    
    def get_curve(self, curve_id: str) -> Optional[FanCurve]:
        """Get a specific curve by ID."""
        return self._fan_curves.get(curve_id)
    
    def get_curve_by_id(self, curve_id: str) -> Optional[FanCurve]:
        """Get a specific curve by ID."""
        return self._fan_curves.get(curve_id)

    def rename_curve(self, curve_id: str, new_name: str) -> bool:
        """Rename a curve by ID. Returns True if successful."""
        if curve_id not in self._fan_curves:
            return False
        
        # Check if new name already exists
        for curve in self._fan_curves.values():
            if curve.name == new_name:
                return False
        
        # Update the curve's name
        self._fan_curves[curve_id].name = new_name
        return True

    def set_curve_sensor(self, curve_id: str, sensor: str) -> bool:
        """Set the sensor for a specific curve by ID. Returns True if successful."""
        if curve_id in self._fan_curves:
            self._fan_curves[curve_id].sensor = sensor
            return True
        return False

    def set_curve_data(self, curve_id: str, data: List[Dict[str, float]]) -> bool:
        """Set the data points for a specific curve by ID. Returns True if successful."""
        if curve_id in self._fan_curves:
            self._fan_curves[curve_id]._data = data
            return True
        return False

    def get_all_curves(self) -> Dict[str, FanCurve]:
        """Get all curves in the profile. Returns dict with curve IDs as keys."""
        return self._fan_curves.copy()

    def get_current_speed(self, backend: 'FanControlBackend' = None) -> Optional[float]:
        """
        Get the current fan speed percentage for this profile based on all assigned sensors.
        Takes the maximum speed from all curves to ensure adequate cooling.
        
        Args:
            backend: FanControlBackend instance to get sensor temperature readings
            
        Returns:
            Maximum fan speed percentage (0-100) from all curves, or None if no curves have sensors
        """
        if not backend:
            return None
        
        max_speed = None
        active_curves = 0
        
        for curve_id, curve in self._fan_curves.items():
            curve_speed = curve.get_current_speed(backend)
            if curve_speed is not None:
                active_curves += 1
                if max_speed is None or curve_speed > max_speed:
                    max_speed = curve_speed
        
        # Return the maximum speed, or 0 if no curves are active
        return max_speed if max_speed is not None else (0.0 if active_curves == 0 and self._fan_curves else None)

    def to_json(self) -> Dict[str, Any]:
        """Serialize profile to JSON format."""
        return {
            "id": self.id,
            "name": self._name,
            "curves": {curve.name: curve.to_json() for curve in self._fan_curves.values()}
        }
    
    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'FanControlProfile':
        """Create a FanControlProfile from JSON data."""
        profile = cls(1)  # Index doesn't matter for loading
        profile.id = data.get("id", str(uuid.uuid4()))  # Use existing ID or generate new one
        profile._name = data.get("name", "Fan Profile")
        profile._fan_curves = {}
        
        curves_data = data.get("curves", {})
        for curve_name, curve_data in curves_data.items():
            curve = FanCurve.from_json(curve_data)
            # Use the curve's ID as the dictionary key
            profile._fan_curves[curve.id] = curve
        
        return profile


class ConfigManager:
    """Manages saving and loading profile configurations to/from JSON files."""
    
    def __init__(self, config_file: str = "fan_profiles_config.json"):
        self.config_file = config_file
        self.config_dir = "config"
        self.config_path = os.path.join(self.config_dir, config_file)
        
        # Ensure config directory exists
        os.makedirs(self.config_dir, exist_ok=True)
    
    def save_profiles(self, profiles_dict: Dict[str, FanControlProfile]) -> bool:
        """Save all profiles to JSON file."""
        try:
            logger.debug(f"save_profiles called with {len(profiles_dict)} profiles")
            logger.debug(f"Config path: {self.config_path}")
            
            config_data = {
                "profiles": {name: profile.to_json() for name, profile in profiles_dict.items()},
                "saved_at": datetime.now().isoformat()
            }
            
            logger.debug(f"Config data prepared, writing to file...")
            
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(config_data, f, indent=2, ensure_ascii=False)
            
            logger.info(f"Saved {len(profiles_dict)} profiles to {self.config_path}")
            return True
        except Exception as e:
            logger.error(f"Error saving profiles: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def load_profiles(self) -> Dict[str, FanControlProfile]:
        """Load all profiles from JSON file."""
        try:
            if not os.path.exists(self.config_path):
                logger.info(f"No config file found at {self.config_path}, starting with default profile")
                return {}
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            profiles = {}
            profiles_data = config_data.get("profiles", {})
            
            for profile_name, profile_data in profiles_data.items():
                profiles[profile_name] = FanControlProfile.from_json(profile_data)
            
            logger.info(f"Loaded {len(profiles)} profiles from {self.config_path}")
            return profiles
            
        except Exception as e:
            logger.error(f"Error loading profiles: {e}")
            return {}
    
    def create_backup(self) -> bool:
        """Create a backup of the current config file."""
        if os.path.exists(self.config_path):
            backup_path = self.config_path + ".bak"
            try:
                import shutil
                shutil.copy2(self.config_path, backup_path)
                logger.info(f"Backup created at {backup_path}")
                return True
            except Exception as e:
                logger.error(f"Error creating backup: {e}")
                return False
        return False


class FanControlBackend:
    """Main backend class that manages the entire fan control system state."""
    
    def __init__(self, config_file: str = "fan_profiles_config.json"):
        self.config_manager = ConfigManager(config_file)
        self.profiles: Dict[str, FanControlProfile] = {}  # Using profile IDs as keys
        
        # Use the global temperature sensor backend instance instead of creating our own
        # This ensures consistency across all components in the application
        self.temperature_backend = None  # Will be set via property access
        
        # Load existing profiles or create default
        self._initialize_profiles()
    
    @property
    def temperature_backend(self):
        """Get the global temperature sensor backend instance."""
        try:
            # Import globals here to avoid circular import
            import globals
            if globals.temp_sensor_service is None:
                logger.warning("Global temperature backend not initialized yet")
                return None
            return globals.temp_sensor_service
        except ImportError:
            logger.warning("Could not import globals module")
            return None
    
    @temperature_backend.setter
    def temperature_backend(self, value):
        """Setter for temperature_backend (used during initialization)."""
        # We don't actually set anything here since we always use the global instance
        pass
    
    def _initialize_profiles(self) -> None:
        """Initialize profiles from config file or create default."""
        loaded_profiles = self.config_manager.load_profiles()
        
        if loaded_profiles:
            # Convert to ID-based dictionary and migrate sensor assignments if needed
            self.profiles = {}
            for profile_name, profile in loaded_profiles.items():
                self.profiles[profile.id] = profile
            
            # Automatically migrate any invalid sensor assignments
            migration_counts = self.auto_migrate_sensor_assignments()
            if migration_counts:
                logger.info(f"Auto-migrated sensor assignments in {len(migration_counts)} profiles")
                # Save the migrated configuration
                self.save_to_config()
        else:
            # Create default profile with real sensors if no config exists
            self._create_default_profile_with_real_sensors()
    
    def _create_default_profile_with_real_sensors(self) -> None:
        """Create a default profile using real temperature sensors."""
        profile_id = self.add_profile()
        profile = self.get_profile(profile_id)
        
        if profile:
            # Only try to assign sensors if temperature backend is available
            if self.temperature_backend is not None:
                try:
                    available_sensors = self.get_available_temperature_sensors()
                    
                    if available_sensors:
                        # Set the first curve to use the first available sensor (preferably CPU)
                        curves = profile._fan_curves
                        if curves:
                            first_curve_id = next(iter(curves.keys()))
                            
                            # Prefer CPU sensors for the default fan curve
                            cpu_sensors = [s for s in available_sensors if 'cpu' in s.lower()]
                            default_sensor = cpu_sensors[0] if cpu_sensors else available_sensors[0]
                            
                            profile.set_curve_sensor(first_curve_id, default_sensor)
                            logger.info(f"Created default profile '{profile._name}' with sensor '{default_sensor}'")
                    else:
                        logger.warning(" No temperature sensors available. Default profile created without sensor assignment.")
                except Exception as e:
                    logger.info(f"Error setting up default profile with sensors: {e}")
                    print("Default profile created without sensor assignment.")
            else:
                logger.warning(" Temperature backend not available. Default profile created without sensor assignment.")
            
            # Always save the configuration after creating the default profile
            # This ensures future page loads will find an existing config file
            try:
                self.save_to_config()
                logger.info(f"Default profile configuration saved to config file")
            except Exception as e:
                logger.error(f"Failed to save default profile configuration: {e}")
    
    def add_profile(self) -> str:
        """Add a new fan profile and return its ID."""
        next_available_id = 1
        while True:
            profile_name = f'Fan Profile {next_available_id}'
            # Check if this name already exists (we still want unique names for display)
            name_exists = any(profile._name == profile_name for profile in self.profiles.values())
            if not name_exists:
                new_profile = FanControlProfile(next_available_id)
                self.profiles[new_profile.id] = new_profile
                return new_profile.id
            next_available_id += 1
    
    def get_profile(self, profile_id: str) -> Optional[FanControlProfile]:
        """Get a profile by ID."""
        return self.profiles.get(profile_id)
    
    def get_profile_by_name(self, profile_name: str) -> Optional[FanControlProfile]:
        """Get a profile by name."""
        for profile in self.profiles.values():
            if profile._name == profile_name:
                return profile
        return None
    
    def remove_profile(self, profile_id: str) -> bool:
        """Remove a profile by ID. Returns True if successful."""
        if len(self.profiles) <= 1:
            return False
        
        if profile_id in self.profiles:
            del self.profiles[profile_id]
            return True
        return False
    
    def rename_profile(self, profile_id: str, new_name: str) -> bool:
        """Rename a profile by ID. Returns True if successful."""
        if profile_id not in self.profiles:
            return False
        
        # Check if new name already exists
        for profile in self.profiles.values():
            if profile._name == new_name:
                return False
        
        # Update the profile's name
        self.profiles[profile_id].set_name(new_name)
        return True
    
    def save_to_config(self) -> bool:
        """Save current state to config file."""
        logger.debug(f" save_to_config called with {len(self.profiles)} profiles")
        
        # Convert ID-based profiles dict to name-based for saving
        profiles_by_name = {}
        for profile_id, profile in self.profiles.items():
            profiles_by_name[profile._name] = profile
            logger.debug(f" Converting profile {profile_id} -> {profile._name}")
        
        logger.debug(f" Calling config_manager.save_profiles with {len(profiles_by_name)} profiles")
        result = self.config_manager.save_profiles(profiles_by_name)
        logger.debug(f" config_manager.save_profiles returned: {result}")
        return result
    
    def reload_from_config(self) -> bool:
        """Reload state from config file, discarding any unsaved changes."""
        self._initialize_profiles()
        return True
    
    def get_profile_names(self) -> List[str]:
        """Get list of all profile names."""
        return [profile._name for profile in self.profiles.values()]
    
    def get_profile_ids(self) -> List[str]:
        """Get list of all profile IDs."""
        return list(self.profiles.keys())
    
    def get_profile_name_by_id(self, profile_id: str) -> Optional[str]:
        """Get profile name by ID."""
        profile = self.profiles.get(profile_id)
        return profile._name if profile else None
    
    def get_profile_id_by_name(self, profile_name: str) -> Optional[str]:
        """Get profile ID by name."""
        for profile_id, profile in self.profiles.items():
            if profile._name == profile_name:
                return profile_id
        return None
    
    def get_curve_names(self, profile_id: str) -> List[str]:
        """Get list of curve names for a specific profile."""
        profile = self.profiles.get(profile_id)
        if profile:
            return [curve.name for curve in profile._fan_curves.values()]
        return []
    
    def get_curve_ids(self, profile_id: str) -> List[str]:
        """Get list of curve IDs for a specific profile."""
        profile = self.profiles.get(profile_id)
        if profile:
            return list(profile._fan_curves.keys())
        return []
    
    def get_curve_name_by_id(self, profile_id: str, curve_id: str) -> Optional[str]:
        """Get curve name by ID within a specific profile."""
        profile = self.profiles.get(profile_id)
        if profile and curve_id in profile._fan_curves:
            return profile._fan_curves[curve_id].name
        return None
    
    def get_curve_id_by_name(self, profile_id: str, curve_name: str) -> Optional[str]:
        """Get curve ID by name within a specific profile."""
        profile = self.profiles.get(profile_id)
        if profile:
            for curve_id, curve in profile._fan_curves.items():
                if curve.name == curve_name:
                    return curve_id
        return None
    
    def get_curve(self, curve_id: str) -> Optional[FanCurve]:
        """Get a curve by ID, searching across all profiles."""
        for profile in self.profiles.values():
            if curve_id in profile._fan_curves:
                return profile._fan_curves[curve_id]
        return None
    
    def get_first_profile_id(self) -> Optional[str]:
        """Get the ID of the first profile (for initialization)."""
        return next(iter(self.profiles.keys())) if self.profiles else None
    
    def get_first_curve_id(self, profile_id: str) -> Optional[str]:
        """Get the ID of the first curve in a profile (for initialization)."""
        profile = self.profiles.get(profile_id)
        if profile:
            curves = profile._fan_curves
            return next(iter(curves.keys())) if curves else None
        return None
    
    def get_first_profile_name(self) -> Optional[str]:
        """Get the name of the first profile (for backward compatibility with UI)."""
        first_id = self.get_first_profile_id()
        if first_id:
            return self.get_profile_name_by_id(first_id)
        return None
    
    def get_first_curve_name(self, profile_name: str) -> Optional[str]:
        """Get the name of the first curve in a profile (for backward compatibility with UI)."""
        # Convert profile name to ID first
        profile_id = self.get_profile_id_by_name(profile_name)
        if profile_id:
            first_curve_id = self.get_first_curve_id(profile_id)
            if first_curve_id:
                return self.get_curve_name_by_id(profile_id, first_curve_id)
        return None
    
    def get_available_temperature_sensors(self) -> List[str]:
        """Get list of all available temperature sensors from hardware."""
        # Check if temperature backend is available
        if self.temperature_backend is None:
            logger.warning(" Temperature backend not available, returning empty sensor list")
            return []

        # Get all sensors from all groups in a flat list
        all_sensors = []
        try:
            sensor_groups = self.temperature_backend.get_sensor_groups()
            
            for group_name, group in sensor_groups.items():
                for sensor_name, sensor in group.sensors.items():
                    if sensor.enabled and sensor.is_hardware_available():
                        # Use format "Group: Sensor Name" for better identification
                        display_name = f"{group_name}: {sensor_name}"
                        all_sensors.append(display_name)
            
            # Add drive temperature monitors
            drive_monitors = self.temperature_backend.get_all_drive_monitors()
            for curve_id, monitor in drive_monitors.items():
                if monitor.enabled and monitor.is_hardware_available():
                    # Use the monitor's name directly for display
                    monitor_name = monitor.name
                    
                    # Check if monitor name already contains status info (to avoid redundancy)
                    if " drives, " in monitor_name:
                        # Monitor name already contains drive count and mode, use as-is
                        display_name = f"Drives.{monitor_name}"
                    else:
                        # Monitor name doesn't contain status info, add it
                        drive_count = monitor.get_available_drive_count()
                        total_count = monitor.get_drive_count()
                        
                        if drive_count > 0:
                            if total_count == drive_count:
                                status = f"{drive_count} drives, {monitor.aggregation_mode}"
                            else:
                                status = f"{drive_count}/{total_count} drives, {monitor.aggregation_mode}"
                            
                            display_name = f"Drives.{monitor_name} ({status})"
                        else:
                            # No available drives, show as disabled
                            display_name = f"Drives.{monitor_name} (no drives available)"
                    
                    all_sensors.append(display_name)
                        
        except AttributeError as e:
            logger.info(f"Error accessing temperature backend: {e}")
            return []

        # If no hardware sensors available, return empty list
        if not all_sensors:
            logger.warning(" No hardware temperature sensors available for fan control")

        return sorted(all_sensors)
    
    def get_temperature_sensor_groups(self) -> Dict[str, List[str]]:
        """Get temperature sensors organized by groups for better UI organization."""
        # Check if temperature backend is available
        if self.temperature_backend is None:
            logger.warning(" Temperature backend not available, returning empty groups")
            return {}
        
        try:
            sensor_groups = self.temperature_backend.get_sensor_groups()
            organized_sensors = {}
            
            for group_name, group in sensor_groups.items():
                group_sensors = []
                for sensor_name, sensor in group.sensors.items():
                    if sensor.enabled and sensor.is_hardware_available():
                        group_sensors.append(sensor_name)
                
                if group_sensors:
                    organized_sensors[group_name] = sorted(group_sensors)
            
            return organized_sensors
        except AttributeError as e:
            logger.info(f"Error accessing temperature backend: {e}")
            return {}
    
    def is_valid_temperature_sensor(self, sensor_display_name: str) -> bool:
        """Check if a sensor display name corresponds to a valid hardware sensor."""
        # Handle drive monitors
        if sensor_display_name.startswith("Drives."):
            if self.temperature_backend is None:
                return False
            
            # Extract monitor name from display name
            monitor_name_with_status = sensor_display_name[7:]  # Remove "Drives." prefix
            
            # Get all drive monitors to check against
            drive_monitors = self.temperature_backend.get_all_drive_monitors()
            
            # Try to find by matching against monitor names
            drive_monitors = self.temperature_backend.get_all_drive_monitors()
            for curve_id, monitor in drive_monitors.items():
                if monitor.name == monitor_name_with_status:
                    return monitor is not None and monitor.enabled and monitor.is_hardware_available()
            
            # If not found, try to match by removing the last parenthetical expression
            if " (" in monitor_name_with_status:
                last_paren_idx = monitor_name_with_status.rfind(" (")
                potential_monitor_name = monitor_name_with_status[:last_paren_idx]
                
                # Try matching against stored monitor names
                for curve_id, monitor in drive_monitors.items():
                    if monitor.name == potential_monitor_name:
                        return monitor is not None and monitor.enabled and monitor.is_hardware_available()
            
            # Final fallback: partial matching
            for curve_id, monitor in drive_monitors.items():
                if (monitor.name in monitor_name_with_status or 
                    monitor_name_with_status in monitor.name):
                    return monitor is not None and monitor.enabled and monitor.is_hardware_available()
            
            return False
        
        # Handle regular sensors
        available_sensors = self.get_available_temperature_sensors()
        return sensor_display_name in available_sensors
    
    def get_sensor_temperature(self, sensor_display_name: str) -> Optional[float]:
        """Get current temperature reading from a sensor by its display name."""
        # Check if temperature backend is available
        if self.temperature_backend is None:
            logger.warning(" Temperature backend not available")
            return None
        
        try:
            # Handle drive monitor format "Drives.Drive Temp (2 drives, maximum)"
            if sensor_display_name.startswith("Drives."):
                # Extract monitor name from display name
                # Format: "Drives.Monitor Name (status info)"
                monitor_name_with_status = sensor_display_name[7:]  # Remove "Drives." prefix
                
                # The monitor name might already contain parentheses (from the original creation)
                # We need to find the actual monitor name by checking what's stored in the backend
                drive_monitors = self.temperature_backend.get_all_drive_monitors()
                
                # Try to find by matching the monitor name
                drive_monitors = self.temperature_backend.get_all_drive_monitors()
                for curve_id, monitor in drive_monitors.items():
                    if monitor.name == monitor_name_with_status:
                        if monitor and monitor.enabled:
                            return monitor.get_current_temperature()
                
                # If not found, try to match by removing the last parenthetical expression
                # This handles cases where extra status info was added during display formatting
                if " (" in monitor_name_with_status:
                    # Find the last occurrence of " (" to remove status info
                    last_paren_idx = monitor_name_with_status.rfind(" (")
                    potential_monitor_name = monitor_name_with_status[:last_paren_idx]
                    
                    # Try matching against stored monitor names
                    for curve_id, monitor in drive_monitors.items():
                        if monitor.name == potential_monitor_name:
                            if monitor and monitor.enabled:
                                return monitor.get_current_temperature()
                
                # Final fallback: partial matching
                for curve_id, monitor in drive_monitors.items():
                    if (monitor.name in monitor_name_with_status or 
                        monitor_name_with_status in monitor.name):
                        if monitor and monitor.enabled:
                            return monitor.get_current_temperature()
                
                return None
            
            # Handle regular sensor format "Group: Sensor Name"
            if ": " not in sensor_display_name:
                return None
            
            group_name, sensor_name = sensor_display_name.split(": ", 1)
            sensor = self.temperature_backend.get_sensor(group_name, sensor_name)
            
            if sensor and sensor.enabled:
                return sensor.get_current_temperature()
        except Exception as e:
            logger.info(f"Error getting temperature for sensor '{sensor_display_name}': {e}")
        
        return None
    
    def refresh_temperature_sensors(self) -> int:
        """Refresh the temperature sensor backend and return count of new sensors found."""
        if self.temperature_backend is None:
            logger.warning(" Temperature backend not available")
            return 0
        
        try:
            return self.temperature_backend.refresh_hardware_sensors()
        except AttributeError as e:
            logger.info(f"Error refreshing temperature sensors: {e}")
            return 0
    
    def get_temperature_sensor_info(self, sensor_display_name: str) -> Optional[Dict[str, Any]]:
        """Get detailed information about a temperature sensor."""
        # Check if temperature backend is available
        if self.temperature_backend is None:
            logger.warning(" Temperature backend not available")
            return None
        
        try:
            if ": " not in sensor_display_name:
                return None
            
            group_name, sensor_name = sensor_display_name.split(": ", 1)
            sensor = self.temperature_backend.get_sensor(group_name, sensor_name)
            
            if sensor:
                return {
                    "name": sensor_name,
                    "group": group_name,
                    "display_name": sensor_display_name,
                    "current_temperature": sensor.get_current_temperature(),
                    "hardware_available": sensor.is_hardware_available(),
                    "hardware_path": sensor.hardware_path,
                    "enabled": sensor.enabled,
                    "last_updated": sensor.last_updated.isoformat() if sensor.last_updated else None
                }
        except Exception as e:
            logger.info(f"Error getting sensor info for '{sensor_display_name}': {e}")
        
        return None
    
    def validate_and_migrate_sensor_assignments(self) -> Dict[str, List[str]]:
        """
        Validate all sensor assignments in profiles and suggest migrations to real sensors.
        Returns a dictionary with profile names as keys and lists of issues as values.
        """
        available_sensors = self.get_available_temperature_sensors()
        issues = {}
        
        for profile_id, profile in self.profiles.items():
            profile_issues = []
            
            for curve_id, curve in profile._fan_curves.items():
                if curve.sensor:
                    # Check if current sensor assignment is valid
                    if curve.sensor not in available_sensors:
                        # Try to find a suitable replacement
                        suggested_sensor = self._suggest_sensor_replacement(curve.sensor, available_sensors)
                        if suggested_sensor:
                            issue = f"Curve '{curve.name}' uses unavailable sensor '{curve.sensor}'. Suggested replacement: '{suggested_sensor}'"
                        else:
                            issue = f"Curve '{curve.name}' uses unavailable sensor '{curve.sensor}'. No suitable replacement found."
                        profile_issues.append(issue)
                else:
                    profile_issues.append(f"Curve '{curve.name}' has no sensor assigned.")
            
            if profile_issues:
                issues[profile._name] = profile_issues
        
        return issues
    
    def _suggest_sensor_replacement(self, old_sensor: str, available_sensors: List[str]) -> Optional[str]:
        """Suggest a replacement sensor based on the old sensor name."""
        if not available_sensors:
            return None
        
        old_sensor_lower = old_sensor.lower()
        
        # Create priority mapping for sensor type matching
        sensor_priorities = []
        
        for sensor in available_sensors:
            sensor_lower = sensor.lower()
            priority = 0
            
            # Exact match gets highest priority
            if old_sensor_lower == sensor_lower:
                return sensor
            
            # CPU sensors
            if any(cpu_term in old_sensor_lower for cpu_term in ['cpu', 'core', 'package']):
                if any(cpu_term in sensor_lower for cpu_term in ['cpu', 'core', 'package']):
                    priority += 10
            
            # GPU sensors
            elif any(gpu_term in old_sensor_lower for gpu_term in ['gpu', 'graphics', 'video']):
                if any(gpu_term in sensor_lower for gpu_term in ['gpu', 'graphics', 'video']):
                    priority += 10
            
            # Storage sensors
            elif any(storage_term in old_sensor_lower for storage_term in ['nvme', 'ssd', 'drive', 'storage']):
                if any(storage_term in sensor_lower for storage_term in ['nvme', 'ssd', 'drive', 'storage']):
                    priority += 10
            
            # System sensors
            elif any(sys_term in old_sensor_lower for sys_term in ['motherboard', 'chipset', 'vrm', 'case', 'ambient']):
                if any(sys_term in sensor_lower for sys_term in ['motherboard', 'chipset', 'vrm', 'case', 'ambient', 'system']):
                    priority += 10
            
            # Partial name matching
            old_words = old_sensor_lower.split()
            for word in old_words:
                if len(word) > 2 and word in sensor_lower:
                    priority += 5
            
            if priority > 0:
                sensor_priorities.append((sensor, priority))
        
        # Return the sensor with highest priority
        if sensor_priorities:
            sensor_priorities.sort(key=lambda x: x[1], reverse=True)
            return sensor_priorities[0][0]
        
        # If no good match found, return the first available sensor
        return available_sensors[0] if available_sensors else None
    
    def auto_migrate_sensor_assignments(self) -> Dict[str, int]:
        """
        Automatically migrate invalid sensor assignments to valid ones where possible.
        Returns a dictionary with profile names as keys and count of migrations as values.
        """
        # Skip migration if temperature backend is not available
        if self.temperature_backend is None:
            logger.warning(" Temperature backend not available, skipping sensor migration")
            return {}
        
        try:
            available_sensors = self.get_available_temperature_sensors()
            migration_counts = {}
            
            for profile_id, profile in self.profiles.items():
                migrations = 0
                
                for curve_id, curve in profile._fan_curves.items():
                    if curve.sensor:
                        # Check if current sensor assignment is invalid
                        if curve.sensor not in available_sensors:
                            # Special handling for drive monitor sensors - don't migrate them if they start with "Drives."
                            if curve.sensor.startswith("Drives."):
                                logger.info(f"Preserving drive monitor sensor assignment: '{curve.sensor}' for curve '{curve.name}' (will be validated later)")
                                # Skip migration for drive monitor sensors - they should be preserved
                                continue
                            
                            suggested_sensor = self._suggest_sensor_replacement(curve.sensor, available_sensors)
                            if suggested_sensor:
                                old_sensor = curve.sensor
                                curve.sensor = suggested_sensor
                                migrations += 1
                                logger.info(f"Migrated curve '{curve.name}' in profile '{profile._name}': '{old_sensor}' → '{suggested_sensor}'")
                    elif available_sensors:
                        # Assign a default sensor if none is assigned
                        # Prefer CPU sensors for the first assignment
                        cpu_sensors = [s for s in available_sensors if 'cpu' in s.lower()]
                        default_sensor = cpu_sensors[0] if cpu_sensors else available_sensors[0]
                        curve.sensor = default_sensor
                        migrations += 1
                        logger.info(f"Assigned default sensor '{default_sensor}' to curve '{curve.name}' in profile '{profile._name}'")
                
                if migrations > 0:
                    migration_counts[profile._name] = migrations
            
            return migration_counts
        except Exception as e:
            logger.info(f"Error during sensor migration: {e}")
            return {}
    
    def get_sensor_statistics(self) -> Dict[str, Any]:
        """Get statistics about available temperature sensors and their usage."""
        available_sensors = self.get_available_temperature_sensors()
        sensor_groups = self.get_temperature_sensor_groups()
        
        # Count sensor usage in profiles
        used_sensors = set()
        total_curves = 0
        curves_with_sensors = 0
        
        for profile in self.profiles.values():
            for curve in profile._fan_curves.values():
                total_curves += 1
                if curve.sensor:
                    curves_with_sensors += 1
                    used_sensors.add(curve.sensor)
        
        return {
            "total_available_sensors": len(available_sensors),
            "sensor_groups": {group: len(sensors) for group, sensors in sensor_groups.items()},
            "total_sensor_groups": len(sensor_groups),
            "used_sensors": len(used_sensors),
            "unused_sensors": len(available_sensors) - len(used_sensors),
            "total_curves": total_curves,
            "curves_with_sensors": curves_with_sensors,
            "curves_without_sensors": total_curves - curves_with_sensors,
            "sensor_usage_percentage": round((len(used_sensors) / len(available_sensors) * 100), 1) if available_sensors else 0,
            "curve_assignment_percentage": round((curves_with_sensors / total_curves * 100), 1) if total_curves else 0
        }
    
    def create_sensor_selection_data(self) -> Dict[str, Any]:
        """Create structured data for temperature sensor selection in UI components."""
        sensor_groups = self.get_temperature_sensor_groups()
        available_sensors = self.get_available_temperature_sensors()
        
        # Create options for dropdowns/selects
        sensor_options = []
        grouped_options = {}
        
        for sensor in available_sensors:
            sensor_options.append({
                "value": sensor,
                "label": sensor,
                "group": sensor.split(": ")[0] if ": " in sensor else "Other"
            })
        
        for group_name, sensors in sensor_groups.items():
            grouped_options[group_name] = [
                {
                    "value": f"{group_name}: {sensor}",
                    "label": sensor,
                    "full_name": f"{group_name}: {sensor}"
                }
                for sensor in sensors
            ]
        
        return {
            "flat_options": sensor_options,
            "grouped_options": grouped_options,
            "total_sensors": len(available_sensors),
            "has_sensors": len(available_sensors) > 0,
            "group_names": list(sensor_groups.keys())
        }
    
    def get_profile_current_speed(self, profile_name: str) -> Optional[float]:
        """
        Get the current fan speed percentage for a specific profile based on all its assigned sensors.
        Takes the maximum speed from all curves in the profile to ensure adequate cooling.
        
        Args:
            profile_name: Name of the profile to calculate speed for
            
        Returns:
            Maximum fan speed percentage (0-100) from all curves in the profile, or None if profile not found
        """
        profile = self.get_profile(profile_name)
        if not profile:
            return None
        
        return profile.get_current_speed(self)
    
    def get_all_profiles_current_speeds(self) -> Dict[str, Optional[float]]:
        """
        Get the current fan speeds for all profiles.
        
        Returns:
            Dictionary mapping profile names to their current speeds (or None if no active curves)
        """
        speeds = {}
        for profile_name in self.profiles.keys():
            speeds[profile_name] = self.get_profile_current_speed(profile_name)
        return speeds
    
    def get_profile_speed_details(self, profile_name: str) -> Optional[Dict[str, Any]]:
        """
        Get detailed speed information for a profile, including per-curve breakdown.
        
        Args:
            profile_name: Name of the profile to analyze
            
        Returns:
            Dictionary with detailed speed information, or None if profile not found
        """
        profile = self.get_profile(profile_name)
        if not profile:
            return None
        
        curve_details = {}
        max_speed = None
        max_curve = None
        active_curves = 0
        total_curves = len(profile._fan_curves)
        
        for curve_id, curve in profile._fan_curves.items():
            curve_speed = curve.get_current_speed(self)
            current_temp = None
            
            if curve.sensor:
                current_temp = self.get_sensor_temperature(curve.sensor)
            
            curve_details[curve_id] = {
                "curve_id": curve_id,
                "curve_name": curve.name,
                "speed": curve_speed,
                "sensor": curve.sensor,
                "current_temperature": current_temp,
                "is_active": curve_speed is not None
            }
            
            if curve_speed is not None:
                active_curves += 1
                if max_speed is None or curve_speed > max_speed:
                    max_speed = curve_speed
                    max_curve = curve_id
        
        return {
            "profile_name": profile_name,
            "max_speed": max_speed,
            "controlling_curve": max_curve,
            "active_curves": active_curves,
            "total_curves": total_curves,
            "curve_details": curve_details,
            "has_active_curves": active_curves > 0
        }


def process_fan_curves_data(curves_data: Dict[str, Any], active_curve: str, visibility: Optional[Dict[str, bool]] = None, fan_backend: Optional[FanControlBackend] = None) -> Dict[str, Any]:
    """
    Process multiple fan curve datasets and print to terminal with real temperature readings.
    This function can be used across different pages that need to process fan curve data.
    """
    print("\n" + "="*70)
    print("MULTI-FAN CURVE DATA RECEIVED")
    print("="*70)
    logger.info(f"⏰ Timestamp: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"Active Curve: {active_curve}")
    logger.info(f"Total Curves: {len(curves_data)}")
    
    if visibility:
        print("\nCurve Visibility:")
        for curve_id, is_visible in visibility.items():
            if curve_id in curves_data:
                status = "Visible" if is_visible else "Hidden"
                logger.info(f"  - {curves_data[curve_id]['name']}: {status}")
    
    for curve_id, curve_info in curves_data.items():
        sensor = curve_info.get('sensor', 'N/A')
        current_temp = None
        
        # Get real temperature reading if fan backend is provided
        if fan_backend and sensor and sensor != 'N/A':
            current_temp = fan_backend.get_sensor_temperature(sensor)
        
        # Display sensor info with current temperature
        sensor_display = sensor if sensor and sensor != 'N/A' else 'No sensor assigned'
        if current_temp is not None:
            sensor_display += f" (Current: {current_temp:.1f}°C)"
        
        logger.info(f"\n{curve_info['name']} ({curve_id})  -->  Sensor: {sensor_display}")
        print("-" * 55)
        
        for i, point in enumerate(curve_info['data'], 1):
            temp = point['x']
            speed = point['y']
            marker = "" if current_temp and abs(temp - current_temp) < 2.0 else ""
            logger.info(f"  Point {i:2d}: {temp:5.1f}°C → {speed:5.1f}%{marker}")
        
        if curve_info['data']:
            temp_range = f"{curve_info['data'][0]['x']:.1f}°C to {curve_info['data'][-1]['x']:.1f}°C"
            min_speed = min(point['y'] for point in curve_info['data'])
            max_speed = max(point['y'] for point in curve_info['data'])
            speed_range = f"{min_speed:.1f}% to {max_speed:.1f}%"
            logger.info(f"📏 Temperature range: {temp_range}")
            logger.info(f"💨 Speed range: {speed_range}")
            
            # Show current fan speed based on temperature if available
            if current_temp is not None:
                current_speed = interpolate_fan_speed(curve_info['data'], current_temp)
                if current_speed is not None:
                    logger.info(f"⚡ Current calculated speed: {current_speed:.1f}% (at {current_temp:.1f}°C)")
    
    print("="*70)
    print("Data processing complete!")
    print("="*70 + "\n")
    
    return {
        "status": "success", 
        "curves_count": len(curves_data),
        "active_curve": active_curve,
        "visibility": visibility
    }


def interpolate_fan_speed(curve_data: List[Dict[str, float]], temperature: float) -> Optional[float]:
    """
    Interpolate fan speed based on temperature using the curve data points.
    
    Args:
        curve_data: List of {"x": temperature, "y": speed} points
        temperature: Current temperature to interpolate speed for
    
    Returns:
        Interpolated fan speed percentage, or None if curve_data is empty
    """
    if not curve_data:
        return None
    
    # Sort curve data by temperature
    sorted_data = sorted(curve_data, key=lambda p: p['x'])
    
    # If temperature is below the first point, return the first speed
    if temperature <= sorted_data[0]['x']:
        return sorted_data[0]['y']
    
    # If temperature is above the last point, return the last speed
    if temperature >= sorted_data[-1]['x']:
        return sorted_data[-1]['y']
    
    # Find the two points to interpolate between
    for i in range(len(sorted_data) - 1):
        x1, y1 = sorted_data[i]['x'], sorted_data[i]['y']
        x2, y2 = sorted_data[i + 1]['x'], sorted_data[i + 1]['y']
        
        if x1 <= temperature <= x2:
            # Linear interpolation
            if x2 == x1:  # Avoid division by zero
                return y1
            
            slope = (y2 - y1) / (x2 - x1)
            interpolated_speed = y1 + slope * (temperature - x1)
            return round(interpolated_speed, 1)
    
    return None


# End of fan_control_backend.py
