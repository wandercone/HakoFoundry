"""
Fan Control Service

This module handles all fan control logic that was previously in the overview page.
It provides a clean interface for managing fan speeds across multiple powerboards
with proper semaphore handling and UI feedback. It also includes integrated fan wall
management for profile-based fan control.
"""

import threading
import json
import os
import logging
from typing import Dict, List, Optional, Any, Callable, TYPE_CHECKING
from nicegui import app, ui, run

# Configure logging
logger = logging.getLogger("foundry_logger")

if TYPE_CHECKING:
    from fan_profile_manager import FanControlBackend, FanControlProfile

# Import the interpolate function from fan_control_backend
try:
    from fan_profile_manager import interpolate_fan_speed
except ImportError:
    # Fallback if interpolate_fan_speed is not available
    def interpolate_fan_speed(curve_data, temperature):
        return None

class FanWall:
    """Represents a single fan wall that can be controlled by a fan profile."""
    
    def __init__(self, wall_id: int, name: str = None, assigned_profile: Optional[str] = None):
        self.wall_id = wall_id
        self.name = name        
        self.assigned_profile = assigned_profile # Profile name
        self.current_speed = 0  # Current fan speed percentage (0-100)
        self.manual: bool = True  # True for manual control, False for profile control
        self._service_ref = None  # Reference to the service for triggering saves
    
    def set_service_reference(self, service):
        """Set reference to the fan control service for triggering config saves."""
        self._service_ref = service
    
    def assign_profile(self, profile_name: Optional[str]) -> None:
        """Assign a fan profile to this wall."""
        self.assigned_profile = profile_name
        logger.info(f"{self.name}: Assigned profile '{profile_name}'")
        
        # Trigger immediate config save if service reference is available
        if self._service_ref:
            self._service_ref.save_config_immediate()
    
class FanControlService:
    """Service class to handle fan control operations and fan wall management."""
    
    def __init__(self):
        """Initialize the fan control service."""
        # Semaphores used to allow only one update of fan PWM to be queued per powerboard
        self.update_pwm_semaphore = threading.Semaphore(1)  # For powerboard 1
        self.update_aux_pwm_semaphore = threading.Semaphore(1)  # For powerboard 2
        
        # Flag to prevent callback loops when updating sliders programmatically
        self.updating_sliders_programmatically = False
        
        # Fan wall management
        self.fan_walls: Dict[int, FanWall] = {}
        self.fan_wall_service_active: bool = False
        
        # Automatic fan control
        self.automatic_control_enabled: bool = False
        self.automatic_control_timer: Optional[ui.timer] = None
        self.automatic_update_interval: float = 2.0  # Update every 2 seconds
        
        # Configuration file path
        self.config_file_path = "config/fan_control_config.json"
        
        # Load configuration on startup
        self._load_config()
        
        # Initialize fan walls based on available powerboards
        self._initialize_fan_walls()
    
    def _load_config(self):
        """Load fan control configuration from file."""
        try:
            if os.path.exists(self.config_file_path):
                with open(self.config_file_path, 'r') as f:
                    self.loaded_config = json.load(f)
                
                # Load automatic control settings
                self.automatic_control_enabled = self.loaded_config.get('automatic_control_enabled', False)
                self.automatic_update_interval = self.loaded_config.get('automatic_update_interval', 2.0)
                self.fan_wall_service_active = self.loaded_config.get('fan_wall_service_active', False)
                
                logger.info("Fan control configuration loaded successfully")
            else:
                logger.info("No fan control config file found, creating default config")
                self.loaded_config = {}
                # Save default configuration for future use
                try:
                    self.save_config_immediate()
                    logger.info("Default fan control configuration saved to config file")
                except Exception as e:
                    logger.error(f"Failed to save default fan control configuration: {e}")
                
        except Exception as e:
            logger.error(f"Error loading fan control config: {e}")
            logger.info("Using default configuration")
            self.loaded_config = {}
    
    def _apply_loaded_config(self):
        """Apply loaded configuration to fan walls after they're initialized."""
        if not hasattr(self, 'loaded_config') or not self.loaded_config:
            return
        
        # Apply fan wall configurations
        fan_walls_config = self.loaded_config.get('fan_walls', {})
        for wall_id_str, wall_config in fan_walls_config.items():
            wall_id = int(wall_id_str)
            if wall_id in self.fan_walls:
                wall = self.fan_walls[wall_id]
                wall.assigned_profile = wall_config.get('assigned_profile', wall.assigned_profile)
                wall.manual = wall_config.get('manual', True)
                # Don't override current_speed from powerboard readings
                logger.info(f"Applied config to {wall.name}: Profile={wall.assigned_profile}, Manual={wall.manual}")
        
        logger.info("Fan wall configuration applied successfully")
    
    def _save_config(self):
        """Save fan control configuration to file."""
        try:
            logger.debug(f"Attempting to save config to: {self.config_file_path}")
            
            # Ensure config directory exists
            config_dir = os.path.dirname(self.config_file_path)
            if not os.path.exists(config_dir):
                os.makedirs(config_dir)
                logger.info(f"Created config directory: {config_dir}")
            
            # Prepare configuration data
            config = {
                'automatic_control_enabled': self.automatic_control_enabled,
                'automatic_update_interval': self.automatic_update_interval,
                'fan_wall_service_active': self.fan_wall_service_active,
                'fan_walls': {}
            }
            
            # Save fan wall configurations
            for wall_id, wall in self.fan_walls.items():
                config['fan_walls'][str(wall_id)] = {
                    'name': wall.name,
                    'assigned_profile': wall.assigned_profile,
                    'manual': wall.manual,
                    'current_speed': wall.current_speed
                }
            
            logger.debug(f"Config data prepared: {len(config['fan_walls'])} fan walls")
            
            # Write to file
            with open(self.config_file_path, 'w') as f:
                json.dump(config, f, indent=4)
            
            logger.info("Fan control configuration saved successfully")
            
        except Exception as e:
            logger.error(f"Error saving fan control config: {e}")
            import traceback
            traceback.print_exc()
    
    def save_config_delayed(self, delay: float = 0.5):
        """Save configuration with a delay to batch multiple rapid changes."""
        # Cancel any existing timer
        if hasattr(self, '_save_timer') and self._save_timer:
            try:
                self._save_timer.cancel()
            except:
                pass  # Timer might already be finished
        
        # Create new timer to save after delay
        def save_and_clear():
            self._save_config()
            self._save_timer = None
            
        self._save_timer = ui.timer(delay, save_and_clear, once=True)
    
    def save_config_immediate(self):
        """Save configuration immediately without delay."""
        # Cancel any pending delayed save
        if hasattr(self, '_save_timer') and self._save_timer:
            try:
                self._save_timer.cancel()
            except:
                pass
            self._save_timer = None
        
        # Save immediately
        self._save_config()
    
    def test_save_config(self):
        """Test method to manually trigger config save for debugging."""
        logger.debug("Manual save test triggered")
        self.save_config_immediate()
        return True
        
    def fan_speed_current(self, pb) -> bool:
        """Check if the fan wall service and up to date."""
        import globals
        # Check first powerboard
        if pb == 1:
            current_fan_speeds = (self.fan_walls[1].current_speed, \
                                self.fan_walls[2].current_speed, \
                                self.fan_walls[3].current_speed)
            if current_fan_speeds != globals.powerboardDict[1].get_running_fan_pwm():
                return False
        # Check second powerboard
        if pb == 2:
            current_aux_speed = self.fan_walls[4].current_speed
            if current_aux_speed != globals.powerboardDict[2].get_running_fan_pwm()[2]:
                return False

        return True
    def update_powerboard_fan_speed(self, pb) -> None:
        """Update the fan speed on the powerboard."""

        import globals
        if pb == 1:
            current_fan_speeds = (self.fan_walls[1].current_speed, \
                                 self.fan_walls[2].current_speed, \
                                 self.fan_walls[3].current_speed)
            globals.powerboardDict[1].update_fan_speed(current_fan_speeds[0], current_fan_speeds[1], current_fan_speeds[2])

        if pb == 2:
            current_aux_speed = self.fan_walls[4].current_speed
            globals.powerboardDict[2].update_fan_speed(current_aux_speed, current_aux_speed, current_aux_speed)

    def _initialize_fan_walls(self):
        """Initialize fan walls based on powerboard availability."""
        import globals  # Import here to avoid circular import
        fan_profiles = self.get_fan_profile_options()
        default_profile = fan_profiles[0] if fan_profiles else None
        
        # Initialize main fan walls if powerboard 1 is available
        if 1 in globals.powerboardDict:
            pb1_queued_fan_speed = globals.powerboardDict[1].get_running_fan_pwm()
            for i in range(1, 4):
                wall_name = f"Fan Wall {i}"
                # Create wall with default values, config will be applied later if it exists
                self.fan_walls[i] = FanWall(i, wall_name, default_profile)
                self.fan_walls[i].set_service_reference(self)  # Set service reference
                self.fan_walls[i].current_speed = pb1_queued_fan_speed[i - 1]
                logger.info(f"Initialized {wall_name}")
            app.timer(3.0, self.ping_powerboards)

        # Initialize auxiliary fan wall if powerboard 2 is available
        if 2 in globals.powerboardDict:
            pb2_queued_fan_speed = globals.powerboardDict[2].get_running_fan_pwm()
            self.fan_walls[4] = FanWall(4, "Auxiliary Fan Wall", default_profile)
            self.fan_walls[4].set_service_reference(self)  # Set service reference
            self.fan_walls[4].current_speed = pb2_queued_fan_speed[2]  # Use third speed for auxiliary wall
            
            logger.info("Initialized Auxiliary Fan Wall")
        
        # Apply loaded configuration after wall initialization
        self._apply_loaded_config()
    
    async def ping_powerboards(self) -> None:

        """Update variables from powerboards."""
        import globals

        if 1 in globals.powerboardDict:
            # Update powerboard state for rpm and wattage
            await run.io_bound(globals.powerboardDict[1].update_powerboard_state)
            # Update queued fan speed if it has changed
            if not self.fan_speed_current(1):
                self.update_powerboard_fan_speed(1)

        if 2 in globals.powerboardDict:
            await run.io_bound(globals.powerboardDict[2].update_powerboard_state)
            if not self.fan_speed_current(2):
                self.update_powerboard_fan_speed(2)
            
        for fan_wall in self.fan_walls.values():
            if not fan_wall.manual:
                fan_wall.current_speed = self._update_single_fan_wall(fan_wall.wall_id)

    def assign_profile_to_wall(self, wall_id: int, profile_name: Optional[str]) -> bool:
        """Assign a fan profile to a specific wall."""
        if wall_id not in self.fan_walls:
            logger.warning(f"Wall {wall_id} does not exist")
            return False
        
        # Validate profile exists if provided
        if profile_name:
            import globals
            if globals.fan_profile_service and not globals.fan_profile_service.get_profile_by_name(profile_name):
                logger.warning(f"Profile '{profile_name}' does not exist")
                return False
        
        self.fan_walls[wall_id].assign_profile(profile_name)
        
        # Save configuration immediately when profile assignment changes
        self.save_config_immediate()
        
        return True
    
    def set_manual_mode(self, wall_id: int, manual: bool = True) -> bool:
        """Set manual mode for a specific fan wall."""
        if wall_id not in self.fan_walls:
            return False
        
        self.fan_walls[wall_id].manual = manual
        mode = "manual" if manual else "profile"
        logger.info(f"{self.fan_walls[wall_id].name} set to {mode} mode")

        # Save configuration immediately when manual mode changes
        self.save_config_immediate()

        return True
    
    def _update_single_fan_wall(self, wall_id: int) -> Optional[float]:
        """Update a single fan wall based on its assigned profile."""
        wall = self.fan_walls.get(wall_id)
        if not wall:
            return None
        
        # If in manual mode, don't update based on profile
        if wall.manual:
            return wall.current_speed
        
        if not wall.assigned_profile:
            # No profile assigned - set to safe default speed
            wall.current_speed = 50
            return 50
        
        import globals
        if not globals.fan_profile_service:
            logger.warning(f"Warning: {wall.name}: Fan backend not available")
            wall.current_speed = 50
            return 50
            
        profile = globals.fan_profile_service.get_profile_by_name(wall.assigned_profile)
        if not profile:
            logger.warning(f"Warning: {wall.name}: Assigned profile '{wall.assigned_profile}' not found")
            
            # Try to assign the next available profile
            available_profiles = self.get_fan_profile_options()
            if available_profiles:
                new_profile = available_profiles[0]  # Get first available profile
                logger.info(f"{wall.name}: Auto-assigning profile '{new_profile}'")
                wall.assign_profile(new_profile)
                
                # Try to get the new profile and update again
                profile = globals.fan_profile_service.get_profile_by_name(new_profile)
                if profile:
                    # Calculate and apply speed from the new profile
                    max_speed = round(self._calculate_max_speed_from_profile(profile))
                    wall.current_speed = max_speed
                    logger.info(f"{wall.name}: Updated speed to {max_speed}% from auto-assigned profile '{new_profile}'")
                    return max_speed
            
            # If no profiles available or assignment failed, use safe default
            wall.current_speed = 50
            return 50
        
        # Calculate maximum speed from all curves in the profile
        max_speed = round(self._calculate_max_speed_from_profile(profile))
        
        # Apply the calculated speed
        wall.current_speed = max_speed
        logger.info(f"{wall.name}: Updated speed to {max_speed}% from profile '{wall.assigned_profile}'")
        
        return max_speed
    
    def _calculate_max_speed_from_profile(self, profile: 'FanControlProfile') -> float:
        """Calculate the maximum fan speed from all curves in a profile."""
        import globals
        
        all_curves = profile.get_all_curves()
        if not all_curves:
            return 50.0  # Safe default
        
        max_speed = 0.0
        curves_with_sensors = 0
        
        for curve_name, curve in all_curves.items():
            if not curve.sensor:
                continue  # Skip curves without sensors
            
            # Get current temperature for this curve's sensor
            current_temp = globals.fan_profile_service.get_sensor_temperature(curve.sensor)
            if current_temp is None:
                continue  # Skip if temperature unavailable
            
            # Calculate fan speed for this curve
            curve_speed = interpolate_fan_speed(curve._data, current_temp)
            if curve_speed is not None:
                max_speed = max(max_speed, curve_speed)
                curves_with_sensors += 1
        
        # If no curves had valid sensors/temperatures, use safe default
        if curves_with_sensors == 0:
            return 50.0
        
        return max_speed
    
    def set_automatic_control_enabled(self, enabled: bool):
        """Enable or disable automatic fan control."""
        if self.automatic_control_enabled != enabled:
            self.automatic_control_enabled = enabled
            logger.info(f"Automatic fan control {'enabled' if enabled else 'disabled'}")
            
            # Save configuration immediately when automatic control setting changes
            self.save_config_immediate()
    
    def set_fan_wall_service_active(self, active: bool):
        """Enable or disable the fan wall service."""
        if self.fan_wall_service_active != active:
            self.fan_wall_service_active = active
            logger.info(f"Fan wall service {'activated' if active else 'deactivated'}")
            
            # Save configuration immediately when service state changes
            self.save_config_immediate()
    
    def set_automatic_update_interval(self, interval: float):
        """Set the automatic update interval."""
        if self.automatic_update_interval != interval:
            self.automatic_update_interval = interval
            logger.info(f"Automatic update interval set to {interval} seconds")
            
            # Save configuration immediately when interval changes
            self.save_config_immediate()
    
    async def _perform_automatic_update(self):
        """Perform automatic fan speed update based on fan profiles."""
        if not self.automatic_control_enabled or not self.fan_wall_service_active:
            return
        
        try:
            # Calculate new speeds for automatic walls
            new_speeds = [None, None, None]  # For walls 1, 2, 3
            any_automatic_walls = False
            
            for wall_id in [1, 2, 3]:
                wall = self.fan_walls.get(wall_id)
                if wall and not wall.manual and wall.assigned_profile:
                    speed = self._update_single_fan_wall(wall_id)
                    if speed is not None:
                        new_speeds[wall_id - 1] = round(speed)
                        any_automatic_walls = True
            
            # If we have automatic walls, update the hardware
            if any_automatic_walls:
                await self._request_update_fan_speed_direct(new_speeds)
                
        except Exception as e:
            logger.error(f"Error in automatic fan control update: {e}")
    
    async def _request_update_fan_speed_direct(self, speeds: List[Optional[float]]):
        """Request fan speed update with direct speed values instead of sliders."""
        # Skip if we're updating sliders programmatically to prevent feedback loops
        if self.updating_sliders_programmatically:
            return
        
        acquired = self.update_pwm_semaphore.acquire(blocking=False)
        if acquired:
            try:
                import globals
                if 1 in globals.powerboardDict:
                    await run.io_bound(globals.powerboardDict[1].semaphore.acquire)
                    globals.powerboardDict[1].semaphore.release()  # Wait for semaphore before grabbing new values
                    
                    # Get current running speeds and update only automatic ones
                    current_pwm = globals.powerboardDict[1].get_running_fan_pwm()
                    row0_pwm = speeds[0] if speeds[0] is not None else current_pwm[0]
                    row1_pwm = speeds[1] if speeds[1] is not None else current_pwm[1]
                    row2_pwm = speeds[2] if speeds[2] is not None else current_pwm[2]
                    
                    # Set the running PWM values
                    globals.powerboardDict[1].set_running_fan_pwm(row0_pwm, row1_pwm, row2_pwm)
                    
                    # Update the powerboard with the latest values
                    await run.io_bound(
                        globals.powerboardDict[1].update_fan_speed, 
                        row0_pwm, 
                        row1_pwm, 
                        row2_pwm
                    )
                    
                    # Only show notification if speeds actually changed
                    changed_walls = []
                    if speeds[0] is not None: changed_walls.append("Wall 1")
                    if speeds[1] is not None: changed_walls.append("Wall 2") 
                    if speeds[2] is not None: changed_walls.append("Wall 3")
                    
                    if changed_walls:
                        ui.notify(
                            f"🤖 Auto: {', '.join(changed_walls)} updated",
                            position='bottom-right', 
                            type='info', 
                            group=False,
                            timeout=1000  # Shorter timeout for auto updates
                        )
                        
            except Exception as e:
                logger.error(f"Error in automatic fan speed update: {e}")
            finally:
                self.update_pwm_semaphore.release()
    
    def get_fan_wall_status(self, wall_id: int) -> Optional[Dict[str, Any]]:
        """Get status of a specific fan wall."""
        wall = self.fan_walls.get(wall_id)
        return wall.get_status() if wall else None
    
    def get_all_fan_walls_status(self) -> Dict[int, Dict[str, Any]]:
        """Get status of all fan walls."""
        return {wall_id: wall.get_status() for wall_id, wall in self.fan_walls.items()}
        
    def set_slider_value_without_callback(self, slider, value: float):
        """Set slider value without triggering the change callback."""
        if slider:
            # Set flag to prevent callback execution
            self.updating_sliders_programmatically = True
            # Set the value
            slider.set_value(value)
            # Reset flag after a short delay to allow any pending events to clear
            ui.timer(0.05, lambda: setattr(self, 'updating_sliders_programmatically', False), once=True)
    
    def get_current_slider_values(self, slider_list: List) -> tuple:
        """Get current slider values safely."""
        return (
            slider_list[0].value if slider_list[0] else 0,
            slider_list[1].value if slider_list[1] else 0,
            slider_list[2].value if slider_list[2] else 0
        )
    
    def get_auxiliary_slider_value(self, slider_list: List) -> float:
        """Get auxiliary slider value safely."""
        return slider_list[3].value if len(slider_list) > 3 and slider_list[3] else 0
    
    async def request_update_fan_speed(self, slider_list: List):
        """Request fan speed update with semaphore protection."""
        # Skip if we're updating sliders programmatically to prevent feedback loops
        if self.updating_sliders_programmatically:
            return
            
        # Get the current slider values right when semaphore becomes available
        def get_current_values():
            return self.get_current_slider_values(slider_list)
        
        acquired = self.update_pwm_semaphore.acquire(blocking=False)
        if acquired:
            try:
                import globals
                if 1 in globals.powerboardDict:
                    await run.io_bound(globals.powerboardDict[1].semaphore.acquire)
                    globals.powerboardDict[1].semaphore.release()  # Wait for semaphore before grabbing new values
                    
                    # Get the latest values right here when semaphore is available
                    row0_pwm, row1_pwm, row2_pwm = get_current_values()
                    
                    # Set the running PWM values
                    globals.powerboardDict[1].set_running_fan_pwm(row0_pwm, row1_pwm, row2_pwm)
                    
                    ui.notify(
                        f"PWM updated {row0_pwm}, {row1_pwm}, {row2_pwm}",
                        position='bottom-right', 
                        type='positive', 
                        group=False
                    )
                    
                    # Update the powerboard with the latest values
                    await run.io_bound(
                        globals.powerboardDict[1].update_fan_speed, 
                        row0_pwm, 
                        row1_pwm, 
                        row2_pwm
                    )
            except Exception as e:
                logger.error(f"Error updating fan speed: {e}")
                ui.notify("Fan speed update failed", position='bottom-right', type='negative', group=False)
            finally:
                self.update_pwm_semaphore.release()

    async def request_update_auxiliary_fan_speed(self, slider_list: List):
        """Request auxiliary fan speed update with UI queue protection for second powerboard."""
        # Skip if we're updating sliders programmatically to prevent feedback loops
        if self.updating_sliders_programmatically:
            return
            
        import globals
        if 2 not in globals.powerboardDict:
            return
        
        # Get the current auxiliary slider value right when semaphore becomes available
        def get_current_aux_value():
            return self.get_auxiliary_slider_value(slider_list)
            
        acquired = self.update_aux_pwm_semaphore.acquire(blocking=False)
        if acquired:
            try:
                pb = globals.powerboardDict[2]
                await run.io_bound(pb.semaphore.acquire)
                pb.semaphore.release()  # Wait for semaphore before updating
                
                # Get the latest auxiliary value right here when semaphore is available
                aux_pwm = get_current_aux_value()
                
                ui.notify(
                    f"Auxiliary PWM updated {aux_pwm}",
                    position='bottom-right', 
                    type='positive', 
                    group=False
                )
                
                # Update the powerboard with the latest value
                await run.io_bound(
                    pb.update_fan_speed, 
                    aux_pwm, 
                    aux_pwm, 
                    aux_pwm
                )
            except Exception as e:
                logger.error(f"Error updating auxiliary fan speed: {e}")
                ui.notify("Auxiliary fan speed update failed", position='bottom-right', type='negative', group=False)
            finally:
                self.update_aux_pwm_semaphore.release()

    async def set_fan_speed(self, row1, row2, row3, aux=100):
        """Set and save fan speed for both powerboards."""
        import globals
        
        # Set powerboard 1 fan speeds
        if 1 in globals.powerboardDict:
            pb1 = globals.powerboardDict[1]
            pb1.set_saved_fan_pwm(row1, row2, row3)

            await run.io_bound(
                globals.powerboardDict[1].set_fan_speed, 
                row1, 
                row2, 
                row3
            )
            pb1.set_running_fan_pwm(row1, row2, row3)
        # Set powerboard 2 fan speeds if it exists and has a slider value
        if 2 in globals.powerboardDict:
            pb2 = globals.powerboardDict[2]
            
            pb2.set_saved_fan_pwm(aux, aux, aux)
            
            await run.io_bound(
                pb2.set_fan_speed,
                aux,
                aux,
                aux
            )
            pb2.set_running_fan_pwm(aux, aux, aux)
        ui.notify("PWM set.", position='bottom-right', type='positive', group=False)

    async def dialog_handler_discard(self, slider_list: List, 
                                   update_fan_speed_callback: Callable,
                                   update_aux_fan_speed_callback: Callable):
        """Handle discarding fan speed changes for both powerboards."""
        import globals
        
        # Reset powerboard 1 values
        if 1 in globals.powerboardDict:
            previous_pwm = globals.powerboardDict[1].get_saved_fan_pwm()
            if len(slider_list) > 2:
                self.set_slider_value_without_callback(slider_list[0], previous_pwm[0])
                self.set_slider_value_without_callback(slider_list[1], previous_pwm[1])
                self.set_slider_value_without_callback(slider_list[2], previous_pwm[2])
                
                await update_fan_speed_callback()
                globals.powerboardDict[1].set_running_fan_pwm(previous_pwm[0], previous_pwm[1], previous_pwm[2])
        
        # Reset powerboard 2 values if it exists
        if 2 in globals.powerboardDict and len(slider_list) > 3:
            previous_aux_pwm = globals.powerboardDict[2].get_saved_fan_pwm()[2]  # Get saved auxiliary speed
            self.set_slider_value_without_callback(slider_list[3], previous_aux_pwm)
            
            # Also update the running PWM on powerboard 2
            await update_aux_fan_speed_callback()
            globals.powerboardDict[2].set_running_fan_pwm(previous_aux_pwm, previous_aux_pwm, previous_aux_pwm)
        
        ui.notify(
            "Fan speeds reset to saved values",
            position='bottom-right', 
            type='positive', 
            group=False
        )

    def check_for_changes(self, slider_list: List) -> bool:
        """Check if current slider values differ from saved powerboard values."""
        import globals
        changes_detected = False
        
        # Check powerboard 1 for changes
        if 1 in globals.powerboardDict:
            pb1 = globals.powerboardDict[1]
            current_values = self.get_current_slider_values(slider_list)
            saved_values = pb1.get_saved_fan_pwm()
            if current_values != saved_values:
                changes_detected = True
        
        # Check powerboard 2 for changes if it exists
        if 2 in globals.powerboardDict and len(slider_list) > 3:
            pb2 = globals.powerboardDict[2]
            saved_aux = pb2.get_saved_fan_pwm()[2]  # Get saved auxiliary speed
            current_aux = self.get_auxiliary_slider_value(slider_list)
            if saved_aux != current_aux:
                changes_detected = True
                
        return changes_detected

    def get_saved_pwm_values(self) -> tuple:
        """Get saved PWM values from powerboards."""
        import globals
        
        pb1_values = (0, 0, 0)
        pb2_value = 0
        
        if 1 in globals.powerboardDict:
            pb1_values = globals.powerboardDict[1].get_saved_fan_pwm()
            
        if 2 in globals.powerboardDict:
            pb2_value = globals.powerboardDict[2].get_saved_fan_pwm()[2]
            
        return pb1_values, pb2_value

    def get_fan_profile_options(self) -> List[str]:
        """Get available fan profile options."""
        import globals
        
        profile_options = []
        if globals.fan_profile_service:
            profile_options = globals.fan_profile_service.get_profile_names()
        return profile_options