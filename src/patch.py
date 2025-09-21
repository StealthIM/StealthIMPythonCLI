# To make IDE happy
# For unknown reason, the following code cannot be warped in a single if TYPE_CHECKING block
from typing import TYPE_CHECKING, cast, TypeVar

from textual.containers import Container
from textual.screen import Screen, ModalScreen

if TYPE_CHECKING:
    from main import IMApp
else:
    class IMApp:
        ...


# noinspection PyRedeclaration
class Screen(Screen):
    SCREEN_NAME: str

    @property
    def app(self) -> IMApp:
        return cast(IMApp, super().app)


class Container(Container):
    @property
    def app(self) -> IMApp:
        return cast(IMApp, super().app)


T = TypeVar("T")


class ModalScreen(ModalScreen[T]):
    SCREEN_NAME: str

    @property
    def app(self) -> IMApp:
        return cast(IMApp, super().app)
