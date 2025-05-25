from foundry_state import Chassis, DriveManager
from powerboard import Powerboard
from nicegui import run
import serial.tools.list_ports

layoutState:Chassis = None
powerboardDict:dict[int, Powerboard] = None
drive_manager:DriveManager = None
drivesList = None
debug = False

def initLayout():
    global layoutState
    layoutState = Chassis("config/foundryConfig.json")

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
        print("Powerboard not found")
    else:
        print(f"Detected {len(powerboardDict)} powerboards.")

def initDrives(debugVal=False):
    global drive_manager
    global drivesList
    drive_manager = DriveManager(debug=debugVal)
    drivesList = drive_manager.get_drives()

async def forceRefreshDrives():
    global drive_manager
    global drivesList
    await run.io_bound(drive_manager.refresh_drives_dict, drivesList)

def initDebug(value:bool):
    global layoutState
    layoutState.debug = value