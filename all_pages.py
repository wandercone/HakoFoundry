from nicegui import ui
from pages.overview_page import overviewPage
from pages.settings_page import settingsPage
"""Class for mapping all pages."""
def create() -> None:
    ui.page('/overview/')(overviewPage)
    ui.page('/settings/')(settingsPage)