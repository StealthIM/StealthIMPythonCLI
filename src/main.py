import dataclasses
import logging
from typing import Optional

from textual.app import App
from textual.logging import TextualHandler

import StealthIM
import db
import screens
from log import logger
from patch import Screen, ModalScreen


def get_screens(module):
    all_screens = []
    for obj_name in dir(module):
        if not obj_name.endswith('Screen'):
            continue
        obj = getattr(module, obj_name)
        if not issubclass(obj, (Screen, ModalScreen)):
            continue
        if obj == Screen or obj == ModalScreen:
            continue
        all_screens.append(obj)
    return all_screens


@dataclasses.dataclass
class AppData:
    server: Optional[StealthIM.Server] = None
    server_db: Optional[db.Server] = None
    user: Optional[StealthIM.User] = None
    user_db: Optional[db.User] = None
    group: Optional[StealthIM.Group] = None


class IMApp(App):
    TITLE = "Stealth IM"
    ALL_SCREENS = [
        *get_screens(screens)
    ]
    SCREENS = {
        screen.SCREEN_NAME: screen for screen in ALL_SCREENS
    }
    BINDINGS = [("ctrl+b", "app_back", "Back")]

    def __init__(self):
        super().__init__()
        self.data = AppData()

    async def on_mount(self) -> None:
        await self.push_screen(screens.ServerSelectScreen.SCREEN_NAME)

    async def action_app_back(self):
        if len(self.screen_stack) > 2:
            await self.pop_screen()


if __name__ == "__main__":
    StealthIM.logger.setLevel(logging.DEBUG)
    StealthIM.logger.addHandler(TextualHandler())

    logger.setLevel(logging.DEBUG)
    logger.addHandler(TextualHandler())

    IMApp().run()
