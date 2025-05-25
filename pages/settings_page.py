from nicegui import ui
from authentication import require_auth
import globals
import page_layout

@require_auth
def settingsPage():
    """Settings page for chassis layout and powerboard information."""
    
    # Use a mutable object to store the flag so it can be accessed in nested functions
    state_flags = {'ignoring_change': False}
    
    def change_product(new_product):
        """Change the chassis product and reset layout."""
        globals.layoutState.reset_chassis()
        globals.layoutState.set_product(new_product)
    
    def handle_product_change(e):
        """Handle product selection change."""
        # Ignore programmatic changes
        if state_flags['ignoring_change']:
            return
            
        current_product = globals.layoutState.get_product()
        new_product = e.value
        
        # Only show dialog if actually changing to a different product
        if new_product != current_product:
            reset_dialog(new_product)
        
    def reset_dialog(new_product):
        """Show confirmation dialog when changing chassis layout."""
        def on_no():
            # Set flag to ignore the change event when resetting value
            state_flags['ignoring_change'] = True
            product_select.set_value(globals.layoutState.get_product())
            state_flags['ignoring_change'] = False
            dialog.close()
            
        with ui.dialog().props('persistent') as dialog, ui.card():
            ui.label('Changing layouts will reset backplanes and drives. Continue?')
            with ui.row().classes('w-full justify-center'):
                ui.button('Yes', on_click=lambda: (change_product(new_product), dialog.close())).classes('border-solid border-2 border-[#ffdd00]').props('flat color="white"')
                ui.button('No', on_click=on_no).classes('border-solid border-2 border-[#ffdd00]').props('flat color="white"')
        dialog.open()
    
    def get_powerboard_info():
        """Get powerboard information for table display."""
        powerboard_data = []
        
        for position in [1, 2]:
            if position in globals.powerboardDict:
                pb = globals.powerboardDict[position]
                try:
                    # Get connection port info
                    port = getattr(pb, '_serial_instance', None)
                    port_name = port.port if port and hasattr(port, 'port') else 'Unknown'
                    
                    powerboard_data.append({
                        'port': port_name,
                        'hardware_rev': pb.hardware_revision if hasattr(pb, 'hardware_revision') else 'Unknown',
                        'firmware_ver': pb.firmware_version if hasattr(pb, 'firmware_version') else 'Unknown',
                        'location': pb.location if hasattr(pb, 'location') else 'Unknown'
                    })
                except Exception as e:
                    # Fallback for any errors accessing powerboard properties
                    powerboard_data.append({
                        'port': 'Error',
                        'hardware_rev': 'Error',
                        'firmware_ver': 'Error',
                        'location': 'Error'
                    })
        
        return powerboard_data
    
    def create_powerboard_table():
        """Create and return powerboard information table."""
        powerboard_data = get_powerboard_info()
        
        if not powerboard_data:
            return ui.label('No powerboards detected.').classes('text-gray-500 italic')
        
        # Define table columns
        columns = [
            {'name': 'port', 'label': 'Serial Port', 'field': 'port', 'required': True, 'align': 'left'},
            {'name': 'hardware_rev', 'label': 'Hardware Rev', 'field': 'hardware_rev', 'required': True, 'align': 'center'},
            {'name': 'firmware_ver', 'label': 'Firmware Ver', 'field': 'firmware_ver', 'required': True, 'align': 'center'},
            {'name': 'location', 'label': 'Location', 'field': 'location', 'required': True, 'align': 'center'}
        ]
        
        return ui.table(
            columns=columns, 
            rows=powerboard_data, 
            row_key='location'
        ).classes('w-full')
    
    # Main settings UI
    with page_layout.frame('Settings'):
        with ui.card().classes('absolute-center') as main_content:
            # Chassis Layout Section
            ui.label('Chassis Configuration').classes('text-xl font-bold mb-4')
            
            with ui.row().classes('items-center gap-4 mb-6'):
                ui.label('Chassis Layout:').classes('font-medium')
                product_select = ui.select(
                    ['Hako-Core', 'Hako-Core Mini'], 
                    value=globals.layoutState.get_product(), 
                    on_change=handle_product_change
                ).classes('w-full')
            
            ui.separator().classes('mb-6')
            
            # Powerboard Information Section
            with ui.column().classes('w-full') as powerboard_container:
                ui.label('Powerboard Information').classes('text-xl font-bold mb-4')
                create_powerboard_table()
            
            # Additional spacing
            ui.space().classes('h-2')