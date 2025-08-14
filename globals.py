from foundry_state import Chassis, DriveManager
from powerboard import Powerboard
from nicegui import run, ui, app
import serial.tools.list_ports
import logging

# Configure logging  
logger = logging.getLogger("foundry_logger")

layoutState:Chassis = None
powerboardDict:dict[int, Powerboard] = None
drive_manager:DriveManager = None
drivesList = None
debug = False

fan_profile_service = None

temp_sensor_service = None

fan_control_service = None

def initLayout():
    global layoutState
    layoutState = Chassis("config/layout_config.json")

def initPowerboard():
    global powerboardDict
    powerboardDict = {}
    # Detect powerboards
    ports = serial.tools.list_ports.comports()

    for onePort in ports:
        if "Arduino Leonardo" in onePort.description:
            pb = Powerboard(onePort.device)
            if (pb.location == 1):
                powerboardDict[1] = pb
            if (pb.location == 2):
                powerboardDict[2] = pb

    if len(powerboardDict) == 0:
        logger.warning("Powerboard not found")
    else:
        logger.info(f"Detected {len(powerboardDict)} powerboards.")

def initDrives(debugVal=False):
    global drive_manager
    global drivesList
    drive_manager = DriveManager(debug=debugVal)
    drivesList = drive_manager.get_drives()
    # Refresh drives every 3 minutes
    ui.timer(180, forceRefreshDrives)

async def forceRefreshDrives():
    global drive_manager
    global drivesList
    await run.io_bound(drive_manager.refresh_drives_dict, drivesList)

def initDebug(value:bool):
    global layoutState
    layoutState.debug = value

def initFanProfileBackend():
    """Initialize the global fan control backend instance."""
    global fan_profile_service
    if fan_profile_service is not None:
        logger.debug("Fan control backend already initialized, skipping")
        return fan_profile_service
    
    import fan_profile_manager
    # Note: Fan backend will use the global temp_backend via property access
    fan_profile_service = fan_profile_manager.FanControlBackend()
    logger.info("Fan control backend initialized (using global temperature backend)")

def initTempBackend():
    """Initialize the global temperature sensor backend instance."""
    global temp_sensor_service
    import temperature_sensor_service
    temp_sensor_service = temperature_sensor_service.SensorManagementService()
    logger.info("Temperature sensor backend initialized")
    
    # Create a timer to refresh temperature readings every 3 seconds
    def refresh_temperatures():
        if temp_sensor_service:
            try:
                temp_sensor_service.update_all_sensors()
                logger.debug("Temperature readings refreshed")
            except Exception as e:
                logger.warning(f"Error refreshing temperature readings: {e}")
    
    ui.timer(3.0, refresh_temperatures)
    logger.info("Temperature refresh timer started (3 second interval)")

def initFanControlService():
    """Initialize the global fan control service instance."""
    global fan_control_service
    
    if fan_control_service is not None:
        logger.info("Fan control service already initialized")
        return fan_control_service
    
    from fan_control_service import FanControlService
    fan_control_service = FanControlService()
    
    logger.info("Fan control service initialized and started")
    return fan_control_service