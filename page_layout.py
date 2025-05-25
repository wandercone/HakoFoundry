from contextlib import contextmanager
from nicegui import ui
import authentication
""" The main layout for every page. Left drawer mainly."""
@contextmanager
def frame(navtitle: str):

    def toggleLeftDrawer():
        left_drawer.props.update(mini=not left_drawer.props.get('mini'))
        left_drawer.update()

    ui.add_css('''
    .text-yellowhako {
    color: #ffdd00 !important;
    }
    .bg-yellowhako {
    color: #ffdd00 !important;
    } 
    ''')

    ui.add_css('''
    .q-drawer {
        transition-property: all;
        transition-duration: 200ms;
        transition-timing-function: ease-in-out;
    }
    .q-drawer-container:not(.q-drawer--mini-animate) .q-drawer--mini .q-item{
        justify-content: left;
        padding-left: 16px;
    }
    ''')

    # Initializing defaults
    ui.icon.default_props('color=yellowhako')
    ui.item_label.default_style('color:white')
    ui.separator.default_props('dark')

    # LEFT
    with ui.left_drawer(bordered=True, top_corner=True).props('mini mini-to-overlay width="300"').style('background-color: #1b1b1b').classes('w-full px-0 p-0').on('mouseenter', lambda: toggleLeftDrawer()).on('mouseleave', lambda: toggleLeftDrawer()) as left_drawer:
        with ui.list().classes('w-full px-0 p-0'):
            with ui.item():
                with ui.item_section().props('avatar'):
                    ui.image('res/Hako_Logo.png').classes('w-6')
                with ui.item_section():
                    ui.item_label('HAKOFORGE FOUNDRY').classes('text-nowrap')

            ui.separator()
            if authentication.get_current_user() == 'Guest':
                with ui.item().props('clickable v-ripple'):
                    with ui.item_section().props('avatar'):
                        ui.icon('person').classes('material-symbols-outlined')
                    with ui.item_section():
                        ui.item_label(f'{authentication.get_current_user()}').classes('text-nowrap')
            else:
                with ui.item().props('clickable v-ripple').on_click(lambda: (authentication.logout_session(), ui.navigate.to('/'))):
                    with ui.item_section().props('avatar'):
                        ui.icon('person').classes('material-symbols-outlined')
                    with ui.item_section():
                        ui.item_label(f'Log Out {authentication.get_current_user()}').classes('text-nowrap')

            ui.separator()

            with ui.item().props('clickable v-ripple').on_click(lambda: ui.navigate.to('/overview')):
                with ui.item_section().props('avatar'):
                    ui.icon('storage').classes('material-symbols-outlined')
                with ui.item_section():
                    ui.item_label('System Overview').classes('text-nowrap')

            ui.separator()
            
            with ui.item().props('clickable').on_click(lambda: ui.navigate.to('/settings')):
                with ui.item_section().props('avatar'):
                    ui.icon('settings').classes('material-symbols-outlined')
                with ui.item_section():
                    ui.item_label('Settings').classes('text-nowrap')

            with ui.item().props('clickable').on_click(lambda: ui.navigate.to('https://docs.hakoforge.com/', new_tab=True)):
                with ui.item_section().props('avatar'):
                    ui.icon('help').classes('material-symbols-outlined')
                with ui.item_section():
                    ui.item_label('Support').classes('text-nowrap')

    yield