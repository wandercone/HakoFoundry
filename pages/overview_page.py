from nicegui import app, ui, run
from authentication import require_auth
from powerboard import Powerboard
import threading
from foundry_state import Chassis, Backplane, Drive
import xxhash
import page_layout
import globals


class DriveButton(ui.button):
    """Custom button class used to select and display drives.
    
    When a drive button is clicked, it gives the option to assign a drive if there is none.
    Once assigned, clicking on the drive will display basic data on the right drawer. 
    Clicking VIEW ALL will pop up a window with raw smartctl data values if there are any.
    Each button is a child of a card element that represents a backplane.
    """
    
    def __init__(self, card, button_index, drive_hash) -> None:
        super().__init__()
        self.selected = False
        self.card = card
        self.button_index = button_index
        
        with self:
            with ui.row().classes('items-center gap-2 w-full overflow-hidden'):
                if drive_hash is None or drive_hash not in globals.drivesList:
                    self.assigned_drive = None
                    self.temp_label = ui.label().classes('flex-shrink-0')
                    self.temp_label.set_visibility(False)
                    self.label = ui.label("----Empty----").style('color: gray').classes(
                        'overflow-hidden whitespace-nowrap text-ellipsis flex-1 min-w-0'
                    ).style('display: inline-block;')
                else:
                    self.assigned_drive: Drive = globals.drivesList.get(drive_hash)
                    self.temp_label = ui.label().bind_text_from(self.assigned_drive, 'temp', lambda temp: f"{temp}°C").classes('flex-shrink-0')
                    self.label = ui.label(self.assigned_drive.model).style('color: white').classes(
                        'overflow-hidden whitespace-nowrap text-ellipsis flex-1 min-w-0'
                    ).style('display: inline-block;')
        
        # This will be set by the parent function
        self.on_click_handler = None

    def assign_drive(self, selection):
        """Assign a drive to this button from selection string."""
        sn = selection.split()[-1][1:-1]
        drive_hash = xxhash.xxh3_64(sn).intdigest()
        self.assigned_drive = globals.drivesList[drive_hash]

        self.label.style('color: white')
        self.label.set_text(self.assigned_drive.model)
        self.temp_label.set_visibility(True)
        self.temp_label.style('color: white')
        self.temp_label.bind_text_from(self.assigned_drive, 'temp', lambda temp: f"{temp}°C")
            
    async def clear_drive(self):
        """Remove the assigned drive from this button."""
        globals.layoutState.remove_drive(self.card, self.assigned_drive.hash)
        self.assigned_drive = None
        self.label.style('color: gray').set_text('----Empty----')
        self.temp_label.set_visibility(False)
        if self.on_click_handler:
            await self.on_click_handler(self)


class HDDButton(DriveButton):
    """Button styled for HDD drives."""
    
    def __init__(self, card, button_index, drive_hash) -> None:
        super().__init__(card, button_index, drive_hash)
        self.props('flat color="white" size="11px"').classes(
            'w-full my-0.5 border-solid border-2 truncate'
        ).style('height: 23%;')


class SmlSSDButton(DriveButton):
    """Button styled for small SSD drives."""
    
    def __init__(self, card, button_index, drive_hash) -> None:
        super().__init__(card, button_index, drive_hash)
        self.props('flat color="white" align="left" size="11px"').classes(
            'w-2/3 my-0.5 px-2 p-1 border-solid border-2 truncate'
        )


class StdSSDButton(DriveButton):
    """Button styled for standard SSD drives."""
    
    def __init__(self, card, button_index, drive_hash) -> None:
        super().__init__(card, button_index, drive_hash)
        self.props('flat color="white" size="11px"').classes(
            'w-full my-0.5 p-0.5 px-1 border-solid border-2 truncate'
        ).style('height: 15%;')


class FansRowButton(ui.button):
    """Button for fan row controls."""
    
    def __init__(self, index) -> None:
        super().__init__()
        self.selected = False
        
        with self.classes(
            'row-span-5 border-solid border-2 flex justify-center items-center px-10 mt-8 w-full w-max:'
        ).props('flat color="white"').style('height: 96%;'):
            if 1 in globals.powerboardDict:
                match index:
                    case 0:
                        self.RPMLabel = ui.label().style('position: fixed; top: 13vh;').bind_text_from(globals.powerboardDict[1], 'row1_rpm', lambda rpm: f'{rpm} RPM')
                    case 1:
                        self.RPMLabel = ui.label().style('position: fixed; top: 13vh;').bind_text_from(globals.powerboardDict[1], 'row2_rpm', lambda rpm: f'{rpm} RPM')
                    case 2:
                        self.RPMLabel = ui.label().style('position: fixed; top: 13vh;').bind_text_from(globals.powerboardDict[1], 'row3_rpm', lambda rpm: f'{rpm} RPM')
            else:
                ui.label('---RPM').style('position: fixed; top: 13vh;')
            ui.icon('mode_fan').props('size="35px"').classes('material-symbols-outlined').style(
                'position: fixed; top: 20vh;'
            )
            ui.icon('mode_fan').props('size="35px"').classes('material-symbols-outlined').style(
                'position: fixed; top: 50vh;'
            )
            ui.icon('mode_fan').props('size="35px"').classes('material-symbols-outlined').style(
                'position: fixed; top: 80vh;'
            )


class WattageCard(ui.card):
    """Card to show wattage info from powerboard."""
    
    def __init__(self, index) -> None:
        super().__init__()
        with self.classes(
            'col-span-3 px-1 p-1 border-2 content-center flex justify-center items-center h-[25px] w-full border-solid border-white border-2'
        ):
            match index:
                case 0:
                    if 1 in globals.powerboardDict:
                        self.watt_label = ui.label().bind_text_from(globals.powerboardDict[1], 'watt_sec_1_2', lambda wattage: f'Row 1: {wattage} watts')
                    else:
                        self.watt_label = ui.label('N/A')
                case 1:
                    if 1 in globals.powerboardDict:
                        self.watt_label = ui.label().bind_text_from(globals.powerboardDict[1], 'watt_sec_3_4', lambda wattage: f'Row 2: {wattage} watts')
                    else:
                        self.watt_label = ui.label('N/A')
                case 2:
                    if 2 in globals.powerboardDict:
                        self.watt_label = ui.label().bind_text_from(globals.powerboardDict[2], 'watt_sec_1_2', lambda wattage: f'Row 3: {wattage} watts')
                    else:
                        self.watt_label = ui.label('N/A')


class StdPlaceHolderCard(ui.card):
    """Standard size card representing standard backplanes."""
    
    def __init__(self, index, backplane: Backplane) -> None:
        super().__init__()
        self.index = index
        self.buttons = []
        
        with self.classes(
            'col-span-3 p-1 border-2 content-center flex justify-center items-center'
        ).style('aspect-ratio: 1/1; width: 100%; max-height: 24vh;'):
            # Will be populated by parent function
            pass


class SmlPlaceHolderCard(ui.card):
    """Small size card representing small backplanes."""
    
    def __init__(self, index, backplane) -> None:
        super().__init__()
        self.index = index
        self.buttons = []
        
        with self.classes(
            'col-span-3 p-1 border-2 content-center flex justify-center items-center h-full'
        ).style('aspect-ratio: 100/87; width: 100%; max-height: 21vh;'):
            # Will be populated by parent function
            pass


class SystemOverview:
    """Main class to handle the system overview page functionality."""
    
    def __init__(self):
        """Initialize the SystemOverview with all necessary state variables."""
        # Global state variables
        self.fan_buttons_list = []
        self.wattage_card_list = []
        self.slider_list = [None] * 6
        self.last_button = None
        self.right_drawer = None
        self.fan_change_dialog = None
        
        # Semaphores used to allow only one update of fan PWM to be queued per powerboard
        self.update_pwm_semaphore = threading.Semaphore(1)  # For powerboard 1
        self.update_aux_pwm_semaphore = threading.Semaphore(1)  # For powerboard 2
        
        # Set up powerboard timer if available
        if 1 in globals.powerboardDict:
            ui.timer(3.0, self.ping_powerboard1)
        if 2 in globals.powerboardDict:
            ui.timer(3.0, self.ping_powerboard2)

        # Refresh drives every 3 minutes
        ui.timer(180, globals.forceRefreshDrives)

    async def ping_powerboard1(self):
        """Update powerboard state periodically."""
        await run.io_bound(globals.powerboardDict[1].update_powerboard_state)

    async def ping_powerboard2(self):
        """Update powerboard state periodically."""
        await run.io_bound(globals.powerboardDict[2].update_powerboard_state)

    def display_full_drive_attributes(self, drive):
        """Display full drive attributes in a dialog."""
        with ui.dialog() as attribute_window, ui.card():
            ui.table(rows=drive.get_attribute_list(), column_defaults={'align': 'left'})
        attribute_window.open()

    def toggle_drive_buttons(self, button):
        """Toggle selection state of drive buttons."""
        if button.selected:  # If selected, deselect and change to white
            button.classes('border-white', remove='border-[#ffdd00]')
            button.selected = False
        else:  # If deselected, select and change to yellow
            button.classes('border-[#ffdd00]', remove='border-white')
            button.selected = True

    async def toggle_fan_buttons(self):
        """Toggle selection state of fan buttons."""
        for button in self.fan_buttons_list:
            if button.selected:  # If selected, deselect and change to white
                button.classes('border-white', remove='border-[#ffdd00]')
                button.selected = False
                self.last_button = button
            else:  # If deselected, select and change to yellow
                button.classes('border-[#ffdd00]', remove='border-white')
                button.selected = True

    async def request_update_fan_speed(self):
        """Request fan speed update with semaphore protection."""
        globals.powerboardDict[1].set_running_fan_pwm(
            self.slider_list[0].value, 
            self.slider_list[1].value, 
            self.slider_list[2].value
        )
        
        acquired = self.update_pwm_semaphore.acquire(blocking=False)
        if acquired:
            try:
                if 1 in globals.powerboardDict:
                    await run.io_bound(globals.powerboardDict[1].semaphore.acquire)
                    globals.powerboardDict[1].semaphore.release()  # Wait for semaphore before grabbing new values
                    
                    ui.notify(
                        f"PWM updated {self.slider_list[0].value}, {self.slider_list[1].value}, {self.slider_list[2].value}",
                        position='bottom-right', 
                        type='positive', 
                        group=False
                    )
                    
                    await run.io_bound(
                        globals.powerboardDict[1].update_fan_speed, 
                        self.slider_list[0].value, 
                        self.slider_list[1].value, 
                        self.slider_list[2].value
                    )
            except Exception as e:
                print(f"Error updating fan speed: {e}")
                ui.notify("Fan speed update failed", position='bottom-right', type='negative', group=False)
            finally:
                self.update_pwm_semaphore.release()

    async def request_update_auxiliary_fan_speed(self):
        """Request auxiliary fan speed update with UI queue protection for second powerboard."""
        if 2 not in globals.powerboardDict:
            return
            
        acquired = self.update_aux_pwm_semaphore.acquire(blocking=False)
        if acquired:
            try:
                pb = globals.powerboardDict[2]
                await run.io_bound(pb.semaphore.acquire)
                pb.semaphore.release()  # Wait for semaphore before updating
                
                ui.notify(
                    f"Auxiliary PWM updated {self.slider_list[3].value}",
                    position='bottom-right', 
                    type='positive', 
                    group=False
                )
                
                await run.io_bound(
                    pb.update_fan_speed, 
                    self.slider_list[3].value, 
                    self.slider_list[3].value, 
                    self.slider_list[3].value
                )
            except Exception as e:
                print(f"Error updating auxiliary fan speed: {e}")
                ui.notify("Auxiliary fan speed update failed", position='bottom-right', type='negative', group=False)
            finally:
                self.update_aux_pwm_semaphore.release()

    async def set_fan_speed(self):
        """Set and save fan speed for both powerboards."""
        # Set powerboard 1 fan speeds
        if 1 in globals.powerboardDict:
            pb1 = globals.powerboardDict[1]

            pb1.set_saved_fan_pwm(
                self.slider_list[0].value, 
                self.slider_list[1].value, 
                self.slider_list[2].value
            )
            
            await run.io_bound(
                globals.powerboardDict[1].set_fan_speed, 
                self.slider_list[0].value, 
                self.slider_list[1].value, 
                self.slider_list[2].value
            )
        
        # Set powerboard 2 fan speeds if it exists and has a slider value
        if 2 in globals.powerboardDict:
            pb2 = globals.powerboardDict[2]

            aux_speed = self.slider_list[3].value
            pb2.set_saved_fan_pwm(aux_speed, aux_speed, aux_speed)
            
            await run.io_bound(
                pb2.set_fan_speed, 
                aux_speed, 
                aux_speed, 
                aux_speed
            )
        
        ui.notify("PWM set.", position='bottom-right', type='positive', group=False)

    async def dialog_handler_discard(self):
        """Handle discarding fan speed changes for both powerboards."""
        # Reset powerboard 1 values
        if 1 in globals.powerboardDict:
            previous_pwm = globals.powerboardDict[1].get_saved_fan_pwm()
            self.slider_list[0].value = previous_pwm[0]
            self.slider_list[1].value = previous_pwm[1]
            self.slider_list[2].value = previous_pwm[2]
            await self.request_update_fan_speed()
            globals.powerboardDict[1].set_running_fan_pwm(self.slider_list[0].value, self.slider_list[1].value, self.slider_list[2].value)
        
        # Reset powerboard 2 values if it exists
        if 2 in globals.powerboardDict:
            previous_aux_pwm = globals.powerboardDict[2].get_saved_fan_pwm()[2]  # Get saved auxiliary speed
            self.slider_list[3].value = previous_aux_pwm
            
            # Also update the running PWM on powerboard 2
            await self.request_update_auxiliary_fan_speed()
            globals.powerboardDict[2].set_running_fan_pwm(previous_aux_pwm,previous_aux_pwm,previous_aux_pwm)
        
        ui.notify(
            "Fan speeds reset to saved values",
            position='bottom-right', 
            type='positive', 
            group=False
        )

    async def select_fans(self, button):
        """Handle fan selection and drawer display."""
        if self.fan_buttons_list[0].selected:  # Closing fan options, check if changes were applied
            changes_detected = False
            
            # Check powerboard 1 for changes
            if 1 in globals.powerboardDict:
                pb1 = globals.powerboardDict[1]
                if pb1.get_saved_fan_pwm() != pb1.get_running_fan_pwm():
                    changes_detected = True
            
            # Check powerboard 2 for changes if it exists
            if 2 in globals.powerboardDict:
                pb2 = globals.powerboardDict[2]
                saved_aux = pb2.get_saved_fan_pwm()[2]  # Get saved auxiliary speed
                current_aux = pb2.get_running_fan_pwm()[2]   # Get current slider value
                if saved_aux != current_aux:
                    changes_detected = True
            
            # If any changes detected, show confirmation dialog
            if changes_detected:
                self.fan_change_dialog.open()
                clicked_option = await self.fan_change_dialog
                if clicked_option is None:
                    return
        
        if self.last_button is None:  # Initial click
            await self.toggle_fan_buttons()
            self.right_drawer.show()
            self.last_button = button
        elif self.last_button in self.fan_buttons_list:  # Fan button clicked
            await self.toggle_fan_buttons()
            self.right_drawer.hide()
            self.last_button = None
            return
        else:  # Last button was a drive 
            self.toggle_drive_buttons(self.last_button)
            await self.toggle_fan_buttons()
            self.last_button = button
        
        self.setup_fan_drawer()

    def setup_fan_drawer(self):
        """Set up the fan control drawer."""
        with self.right_drawer:
            self.right_drawer.clear()

            if not globals.powerboardDict:
                with ui.row().classes('w-full justify-center p-12'):
                    ui.label('No powerboards detected.').classes('text-gray-500 italic')
                return
                
            if 1 in globals.powerboardDict:  # Display fan speeds
                pb: Powerboard = globals.powerboardDict[1]
                pwm_tuple = pb.get_saved_fan_pwm()
                row0_pwm, row1_pwm, row2_pwm = pwm_tuple

                ui.label('Row 1 Fans').tooltip('Bulk fan header hidden under first powerboard.').classes('m-5')
                with ui.element('div').classes('px-5 pt-4 w-full '):
                    self.slider_list[0] = ui.slider(
                        min=20, max=100, value=row0_pwm
                    ).props('label-always').on('change', self.request_update_fan_speed)
                    
                ui.separator()
                ui.label('Row 2 Fans').tooltip('Bulk fan header hidden under first powerboard.').classes('mx-5 mb-5')
                with ui.element('div').classes('px-5 pt-1 w-full'):
                    self.slider_list[1] = ui.slider(
                        min=20, max=100, value=row1_pwm
                    ).props('label-always').on('change', self.request_update_fan_speed)
                
                ui.separator()
                ui.label('Row 3 Fans').tooltip('Fan headers on the first powerboard.').classes('mx-5 mb-5')
                with ui.element('div').classes('px-5 pt-1 w-full'):
                    self.slider_list[2] = ui.slider(
                        min=20, max=100, value=row2_pwm
                    ).props('label-always').on('change', self.request_update_fan_speed)
                
                ui.separator()
            
            if 2 in globals.powerboardDict:  # Display auxiliary fan control
                pb: Powerboard = globals.powerboardDict[2]
                # Get current saved auxiliary fan speed from powerboard 2
                aux_pwm_tuple = pb.get_saved_fan_pwm()
                aux_pwm = aux_pwm_tuple[2]  # Use row 3 as the auxiliary speed
                ui.label('Auxiliary Fans').tooltip('Fan headers on the second powerboard.').classes('mx-5 mb-5')
                with ui.element('div').classes('px-5 pt-1 w-full'):
                    self.slider_list[3] = ui.slider(
                        min=20, max=100, value=aux_pwm
                    ).props('label-always').on('change', self.request_update_auxiliary_fan_speed)
                ui.separator()
            with ui.element('div').classes('px-4 w-full'):
                ui.button('Apply', on_click=self.set_fan_speed).props(
                    'color="white" flat'
                ).classes('w-full border-solid border-2 border-[#ffdd00]').props('flat color="white"')

    def update_ui_elements(self):
        """Update RPM and wattage display elements."""
        if 1 in globals.powerboardDict:
            rpm_tuple = globals.powerboardDict[1].get_fan_tach()
            self.fan_buttons_list[0].RPMLabel.set_text(str(rpm_tuple[0] * 75) + "RPM")
            self.fan_buttons_list[1].RPMLabel.set_text(str(rpm_tuple[1] * 75) + "RPM")
            
            if globals.layoutState.get_product() == "Hako-Core":
                self.fan_buttons_list[2].RPMLabel.set_text(str(rpm_tuple[2] * 75) + "RPM")

            watt_tuple = globals.powerboardDict[1].get_power_usage()
            watt_row1 = round(watt_tuple[0] + watt_tuple[1])
            watt_row2 = round(watt_tuple[2] + watt_tuple[3])
            self.wattage_card_list[0].watt_label.set_text(f"Row 1: {watt_row1} Watts")
            self.wattage_card_list[1].watt_label.set_text(f"Row 2: {watt_row2} Watts")
        else:
            self.fan_buttons_list[0].RPMLabel.set_text("N/A")
            self.fan_buttons_list[1].RPMLabel.set_text("N/A")
            
            if globals.layoutState.get_product() == "Hako-Core":
                self.fan_buttons_list[2].RPMLabel.set_text("N/A")

            self.wattage_card_list[0].watt_label.set_text("N/A")
            self.wattage_card_list[1].watt_label.set_text("N/A")

        if 2 in globals.powerboardDict and globals.layoutState.get_product() == "Hako-Core":
            watt_tuple = globals.powerboardDict[2].get_power_usage()
            watt_row3 = watt_tuple[0] + watt_tuple[1]
            self.wattage_card_list[2].watt_label.set_text(f"Row 3: {watt_row3} Watts")
        else:
            if globals.layoutState.get_product() == "Hako-Core":
                self.wattage_card_list[2].watt_label.set_text("N/A")

    def display_drive_attributes(self, button: DriveButton):
        """Display drive attributes in the right drawer."""
        self.right_drawer.clear()
        
        with self.right_drawer:
            columns = [
                {'name': 'attribute', 'label': 'Attribute', 'field': 'attribute', 'required': True, 'align': 'left'},
                {'name': 'value', 'label': 'Value', 'field': 'value', 'required': True, 'align': 'right'},
            ]
            
            d = button.assigned_drive
            rows = [
                {'attribute': 'Model', 'value': d.model},
                {'attribute': 'SN', 'value': d.serial_num},
                {'attribute': 'Firmware', 'value': d.firmware_ver},
                {'attribute': 'Capacity', 'value': d.capacity},
                {'attribute': 'Rotation Speed', 'value': d.rotate_rate},
                {'attribute': 'Power On Time', 'value': d.on_time},
                {'attribute': 'Start Stop Count', 'value': d.power_cycle},
                {'attribute': 'Temp', 'value': d.temp}
            ]

            with ui.item().props('clickable v-ripple').classes('w-full bg-[#ffdd00]').on(
                'mouseenter', lambda: edit_icon.set_visibility(True)
            ).on('mouseleave', lambda: edit_icon.set_visibility(False)):
                with ui.item_section():
                    ui.item_label(d.model).style('color: black')
                with ui.item_section().props('avatar'):
                    edit_icon = ui.icon('edit').props('color=black').classes('material-symbols-outlined')
                    edit_icon.set_visibility(False)
                with ui.menu().props('fit'):
                    ui.menu_item('Remove drive', lambda: button.clear_drive())
            
            ui.table(columns=columns, rows=rows, row_key='attribute').classes('w-full')
            with ui.element('dive').classes('w-full px-4'):
                ui.button(
                    "Show All", 
                    icon='open_in_new', 
                    on_click=lambda: self.display_full_drive_attributes(d)
                ).classes('w-full border-solid border-2 border-[#ffdd00]').props('flat color="white"')

    async def select_drive(self, button: DriveButton):
        """Handle drive selection and drawer display."""
        if self.last_button is None:  # Initial click
            self.toggle_drive_buttons(button)
            self.right_drawer.show()
            self.last_button = button
        elif self.last_button in self.fan_buttons_list:  # Last click was fans
            await self.toggle_fan_buttons() 
            self.toggle_drive_buttons(button)
            self.last_button = button
        elif self.last_button == button:  # Same button clicked, deselect
            self.toggle_drive_buttons(button)
            self.right_drawer.hide()
            self.last_button = None
        else:  # General switching selection
            self.toggle_drive_buttons(self.last_button)
            self.toggle_drive_buttons(button)
            self.last_button = button

        if button.assigned_drive is None:  # No drive assigned, display options
            self.setup_drive_assignment_drawer(button)
        else:
            self.display_drive_attributes(button)

    def setup_drive_assignment_drawer(self, button: DriveButton):
        """Set up the drive assignment drawer."""
        with self.right_drawer:
            self.right_drawer.clear()
            
            with ui.item().classes('w-full bg-[#ffdd00]'):
                with ui.item_section():
                    ui.item_label("Assign Drive").style('color: black')
            with ui.element('div').classes('p-4 w-full'):
                ui.select(
                    label="Select or search drive",
                    options=[
                        globals.drivesList[k].model + ' (' + globals.drivesList[k].serial_num + ')' 
                        for k in globals.drivesList
                    ], 
                    with_input=True,
                    on_change=lambda e: (
                        button.assign_drive(e.value), 
                        globals.layoutState.insert_drive(button.card, e.value, button.button_index), 
                        self.display_drive_attributes(button)
                    )
                ).classes('w-full')

    def setup_backplane_buttons(self, card, backplane: Backplane, backplane_type: str):
        """Set up buttons for different backplane types."""
        card.clear()
        
        backplane_configs = {
            "STD4HDD": {
                "buttons": 4,
                "button_class": HDDButton,
                "layout": "single_column"
            },
            "STD12SSD": {
                "buttons": 12,
                "button_class": StdSSDButton,
                "layout": "two_column"
            },
            "SML2+2": {
                "buttons": 4,
                "button_class": [HDDButton, HDDButton, SmlSSDButton, SmlSSDButton],
                "layout": "mixed"
            }
        }
        
        config = backplane_configs.get(backplane_type)
        if not config:
            return
            
        with card:
            if config["layout"] == "single_column":
                with ui.element('div').classes('h-full flex items-center justify-center'):
                    for i in range(config["buttons"]):
                        button = config["button_class"](card, i, backplane.drives_hashes[i])
                        button.on_click_handler = self.select_drive
                        button.on('click', lambda b=button: self.select_drive(b))
                        card.buttons.append(button.classes('truncate'))
                        
            elif config["layout"] == "two_column":
                with ui.element('div').classes('grid grid-cols-2 gap-1 flex items-center justify-center h-full'):
                    with ui.element('col1').classes('col-span-1 h-full'):
                        for i in range(6):
                            button = config["button_class"](card, i, backplane.drives_hashes[i])
                            button.on_click_handler = self.select_drive  
                            button.on('click', lambda b=button: self.select_drive(b))
                            card.buttons.append(button.classes('truncate'))
                    with ui.element('col2').classes('col-span-1 h-full'):
                        for i in range(6, 12):
                            button = config["button_class"](card, i, backplane.drives_hashes[i])
                            button.on_click_handler = self.select_drive
                            button.on('click', lambda b=button: self.select_drive(b))
                            card.buttons.append(button.classes('truncate'))
                            
            elif config["layout"] == "mixed":
                with ui.element('div').classes('h-full flex items-center justify-center'):
                    for i in range(4):
                        button_class = config["button_class"][i]
                        button = button_class(card, i, backplane.drives_hashes[i])
                        button.on_click_handler = self.select_drive
                        button.on('click', lambda b=button: self.select_drive(b))
                        if i >= 2:  # SSD buttons
                            button.props('no-wrap')
                        card.buttons.append(button)
            
            with ui.context_menu():
                ui.menu_item(
                    'Remove Backplane', 
                    on_click=lambda: (
                        globals.layoutState.remove_backplane(card), 
                        self.add_backplane_button(card, card.__class__)
                    )
                )

    def add_backplane_button(self, card, card_class):
        """Add backplane selection button to empty card."""
        card.clear()
        
        # Clear any selected buttons
        for button in card.buttons:
            if button.selected:
                self.last_button = None
                self.right_drawer.hide()
        card.buttons.clear()
        
        with card:
            if card_class == StdPlaceHolderCard:
                with ui.dropdown_button('Add Backplane').props('outline color="grey"'):
                    ui.item(
                        '4 HDD Backplane', 
                        on_click=lambda: self.setup_backplane_buttons(
                            card, 
                            globals.layoutState.insert_backplane(card, "STD4HDD"), 
                            "STD4HDD"
                        )
                    )
                    ui.item(
                        '12 SSD Backplane', 
                        on_click=lambda: self.setup_backplane_buttons(
                            card, 
                            globals.layoutState.insert_backplane(card, "STD12SSD"), 
                            "STD12SSD"
                        )
                    )
            else:  # SmlPlaceHolderCard
                with ui.dropdown_button('Add Backplane').props('outline color="grey"'):
                    ui.item(
                        '2+2 Backplane', 
                        on_click=lambda: self.setup_backplane_buttons(
                            card, 
                            globals.layoutState.insert_backplane(card, "SML2+2"), 
                            "SML2+2"
                        )
                    )

    def create_chassis_layout(self, card: ui.card, chassis_type: str):
        """Create chassis layout based on type."""
        if globals.layoutState.get_product() is None:
            globals.layoutState.set_product(chassis_type)

        card.clear()
        self.fan_buttons_list.clear()
        self.wattage_card_list.clear()
        
        layout_configs = {
            "Hako-Core": {
                "grid_cols": 12,
                "fan_buttons": 3,
                "wattage_cards": 3,
                "std_cards": 9,
                "sml_cards": 3
            },
            "Hako-Core Mini": {
                "grid_cols": 8,
                "fan_buttons": 2,
                "wattage_cards": 2,
                "std_cards": 6,
                "sml_cards": 2
            }
        }
        
        config = layout_configs[chassis_type]
        
        card.classes(
            f'self-center grid grid-cols-{config["grid_cols"]} py-0 gap-0.5 justify-items-center'
        ).style('max-height: 96.5vh; width: 60vw; min-width: 800px')
        
        with card:
            # Create fan buttons and wattage cards
            for i in range(config["fan_buttons"]):
                fan_button = FansRowButton(i)
                fan_button.on('click', lambda b=fan_button: self.select_fans(b))
                self.fan_buttons_list.append(fan_button)
                
                if i < config["wattage_cards"]:
                    self.wattage_card_list.append(WattageCard(i))

            # Create backplane cards
            if not globals.layoutState.is_empty():
                backplane_list = globals.layoutState.get_backplanes()
                
                # Standard cards
                for i, bp in enumerate(backplane_list[:config["std_cards"]]):
                    card_widget = StdPlaceHolderCard(i, bp)
                    if bp:
                        self.setup_backplane_buttons(card_widget, bp, bp.product)
                    else:
                        self.add_backplane_button(card_widget, StdPlaceHolderCard)
                
                # Small cards
                start_idx = 9 if chassis_type == "Hako-Core" else 6
                for i, bp in enumerate(backplane_list[start_idx:start_idx + config["sml_cards"]]):
                    card_widget = SmlPlaceHolderCard(i + start_idx, bp)
                    if bp:
                        self.setup_backplane_buttons(card_widget, bp, bp.product)
                    else:
                        self.add_backplane_button(card_widget, SmlPlaceHolderCard)
            else:
                # Create empty cards
                for i in range(config["std_cards"]):
                    card_widget = StdPlaceHolderCard(i, None)
                    self.add_backplane_button(card_widget, StdPlaceHolderCard)
                
                for i in range(config["sml_cards"]):
                    card_widget = SmlPlaceHolderCard(i + (9 if chassis_type == "Hako-Core" else 6), None)
                    self.add_backplane_button(card_widget, SmlPlaceHolderCard)
        
        # Start update timer
        #ui.timer(3.0, lambda: self.update_ui_elements())

    def create_ui(self):
        """Create the main UI."""
        with page_layout.frame('System Overview'):
            with ui.card().classes('absolute-center') as main_content:
                current_chassis = globals.layoutState.get_product()
                
                if current_chassis is None:
                    ui.label('Select chassis:').classes('w-full')
                    with ui.row().classes('items-center gap-4 mb-6'):
                        ui.button(
                            'Hako-Core', 
                            on_click=lambda: self.create_chassis_layout(main_content, "Hako-Core")
                        ).classes('border-solid border-2 border-[#ffdd00]').props('flat color="white"')
                        ui.button(
                            'Hako-Core Mini', 
                            on_click=lambda: self.create_chassis_layout(main_content, "Hako-Core Mini")
                        ).classes('border-solid border-2 border-[#ffdd00]').props('flat color="white"')
                elif current_chassis in ["Hako-Core", "Hako-Core Mini"]:
                    self.create_chassis_layout(main_content, current_chassis)

            # Create drawers and dialogs
            self.right_drawer = ui.right_drawer(value=False, fixed=True).style().props(
                'bordered width="500"'
            ).classes('p-0')

            with ui.dialog() as self.fan_change_dialog, ui.card():
                ui.label('Apply changes?')
                ui.button(
                    'Apply', 
                    on_click=lambda: self.fan_change_dialog.submit("Apply")
                ).on_click(self.set_fan_speed)
                ui.button(
                    'Discard', 
                    on_click=lambda: self.fan_change_dialog.submit("Discard")
                ).on_click(self.dialog_handler_discard)

@require_auth
def overviewPage():
    """Page with helper-functions that interact with the powerboard and use smartctl to display GUI.

    The powerboard is an object that gets refreshed every 3 seconds for new values and the respective
    UI elements are updated. During the refresh, the powerboard is unable to take commands for 2 seconds.
    Fan control commands are queued if the powerboard is busy. A toast notification will popup indicating 
    a fan command has been executed.

    The drive information is taken from smartctl commands so S.M.A.R.T. must be enabled on the drives to
    be shown. 
    """
    overview = SystemOverview()
    overview.create_ui()