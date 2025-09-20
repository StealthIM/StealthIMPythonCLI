from textual import on, events
from textual.events import Key, Click
from textual.containers import VerticalScroll, Right
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, Markdown, Static, ListView, ListItem

import StealthIM
import db
from .common import CondManage, MessageData


class ScrolledToTop(events.Event):
    ...


class TopDetectingScroll(VerticalScroll):
    do_watching = reactive(True)

    def watch_scroll_y(self, old: float, new: float) -> None:
        super().watch_scroll_y(old, new)
        threshold = 0.001
        if (new <= threshold) and (old is None or old > threshold) and self.do_watching:
            self.do_watching = False
            self.post_message(ScrolledToTop())

    def reset_watching(self):
        self.do_watching = True


class ChatMessage(Static):
    def __init__(self, message: MessageData, user: db.User) -> None:
        me = message.username == user.username
        super().__init__(classes='me' if me else 'other')

        self.text = message.msg
        self.nickname = message.nickname
        self.me = me
        self.time = message.time
        self.msgid = message.msgid
        self.type = message.type

    def compose(self):
        align = "right" if self.me else "left"
        with CondManage(self.me, Right):
            yield Label(f"{self.nickname} {self.time}", id="meta", classes=f"meta {align}")
        with CondManage(self.me, Right):
            if self.type == StealthIM.apis.message.MessageType.Text.value:
                yield Markdown(self.text, id="message", classes=f"msg {'me' if self.me else 'other'}")
            else:
                yield Label("不支持的消息类型", id="message")

class FocusableLabel(Label):
    DEFAULT_CSS = """
    FocusableLabel {
        color: white;
        background: grey;
    }

    FocusableLabel:focus {
        color: black;
        background: white;
    }
    """
    can_focus = True

    class Clicked(Message, bubble=True):
        ...

    def get_absolute_position(self, widget: Widget) -> tuple[int, int]:
        x, y = widget.region.x, widget.region.y
        self.log(f"Parent: {widget}, (x, y):{x, y}")
        parent = widget.parent
        while parent is not None:
            if hasattr(parent, 'region'):
                self.log(f"Parent: {parent}, (x, y):{parent.region.x, parent.region.y}")
                x += parent.region.x
                y += parent.region.y
            parent = parent.parent
        return x, y

    async def on_key(self, event: events.Key) -> None:
        if event.key in ("enter", "space"):
            x, y = self.get_absolute_position(self)
            self.log(f"-----------------------------------------------")
            self.log(f"x, y: {x, y}")
            self.log(f"-----------------------------------------------")
            self.post_message(
                events.Click(self, x, y, 0, 0, 1, False, False, False)
            )
            event.stop()


class ReactiveListView(ListView):
    selected: reactive[None] = reactive(None, init=False, always_update=True)

    def __init__(
            self,
            *children: ListItem,
            initial_index: int | None = 0,
            name: str | None = None,
            id: str | None = None,
            classes: str | None = None,
            disabled: bool = False,
    ) -> None:
        super().__init__(*children,
                         initial_index=initial_index, name=name, id=id, classes=classes, disabled=disabled)

    @on(ListView.Selected)
    def on_changed(self, event) -> None:
        self.selected = None


class Popup(Widget):
    class Command(Message):
        def __init__(self, name: str) -> None:
            super().__init__()
            self.name = name

    def __init__(self, text: str, *items: tuple[str, str], id: str | None = None) -> None:
        super().__init__(id=id)
        self.label = FocusableLabel(text)
        self.items = items
        self._menu: ReactiveListView | None = None
        self.styles.width = "auto"
        self.styles.height = "auto"

    def compose(self):
        yield self.label

    async def show_menu(self, event: events.Click) -> None:
        max_text_len = max(len(label) for label, _ in self.items)
        menu_width = max_text_len + 6
        menu_height = len(self.items) + 2

        menu = ReactiveListView(
            *[ListItem(Label(label), id=name) for label, name in self.items],
        )
        self._menu = menu

        menu.styles.border = ("round", "green")
        menu.styles.width = menu_width
        menu.styles.height = menu_height
        menu.styles.position = "absolute"
        menu.styles.layer = "overlay"
        menu.styles.offset = event.screen_x, event.screen_y

        self.watch(menu, "selected", self.on_selected)

        menu.focus()

        await self.app.screen.mount(menu)

    async def close_menu(self) -> None:
        if self._menu:
            await self._menu.remove()
            self._menu = None

    async def on_selected(self) -> None:
        self.log("Selected0")
        if not self._menu or self._menu.index is None:
            return
        self.log("Selected1")
        self.post_message(
            self.Command(self.items[self._menu.index][1]),
        )
        await self.close_menu()

    async def on_global_click(self, event: events.Click) -> None:
        if event.widget == self.label or event.widget == self._menu:
            return
        if self._menu:
            await self.close_menu()

    @on(Click)
    async def on_click(self, event: events.Click) -> None:
        if event.widget == self.label:
            await self.show_menu(event)

    async def on_global_key(self, event: events.Key) -> None:
        if event.key not in ("up", "down", "enter") and self._menu:
            await self.close_menu()

    # noinspection PyUnresolvedReferences,PyProtectedMember
    def on_mount(self) -> None:
        if not hasattr(self.app.screen, "_popup_callback_click"):
            self.app.screen._popups = []

            # noinspection PyUnresolvedReferences
            async def callback(_self, event: Click) -> None:
                for obj in self.app.screen._popups:
                    await obj.on_global_click(event)
            self.app.screen._popup_callback_click = callback
            self.app.screen._decorated_handlers.setdefault(Click, [])
            self.app.screen._decorated_handlers[Click].append((callback, None))
        if not hasattr(self.app.screen, "_popup_callback_key"):
            self.app.screen._popups = []

            # noinspection PyUnresolvedReferences
            async def callback(_self, event: Key) -> None:
                for obj in self.app.screen._popups:
                    await obj.on_global_key(event)
            self.app.screen._popup_callback_key = callback
            self.app.screen._decorated_handlers.setdefault(Key, [])
            self.app.screen._decorated_handlers[Key].append((callback, None))
        self.app.screen._popups.append(self)

    # noinspection PyUnresolvedReferences,PyProtectedMember
    def on_unmount(self) -> None:
        self.app.screen._popups.remove(self)
