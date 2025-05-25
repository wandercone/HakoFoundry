import all_pages
import authentication
import globals
import os
import hashlib
from nicegui import ui

@ui.page('/')
def index_page() -> None:
    if authentication.validate_environment():
        authentication.create_login_page()
    else:
        ui.navigate.to('/overview')

all_pages.create()

# Initializing things that only run once.
if __name__ == '__mp_main__':
    globals.initLayout()
    globals.initPowerboard()
    if os.getenv('DEBUG') == 'TRUE':
        globals.initDrives(True)
    else:
        globals.initDrives()

    # No authentication provided, open site
    authentication.validate_environment()

ui.run(title="Hako Foundry", favicon="res/Hako_Logo.png", dark=True, storage_secret=hashlib.sha256((os.getenv('ADMIN_PASSWORD') if os.getenv('ADMIN_PASSWORD') else 'Default').encode()).hexdigest())