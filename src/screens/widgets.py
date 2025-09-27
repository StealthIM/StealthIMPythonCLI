from textual import events, on
from textual.app import ComposeResult
from textual.containers import Container, Right, VerticalScroll
from textual.events import Click, Key
from textual.message import Message
from textual.reactive import reactive
from textual.widget import Widget
from textual.widgets import Label, ListItem, ListView, Markdown, Static

import StealthIM
import db
from .common import CondManage, MessageData


class TopDetectingScroll(VerticalScroll):
    do_watching = reactive(True)

    class ScrolledToTop(events.Event):
        def __init__(self, control: "TopDetectingScroll") -> None:
            super().__init__()
            self.self = control  # For Textual event routing

        @property
        def control(self) -> "TopDetectingScroll":
            return self.self

    def watch_scroll_y(self, old: float, new: float) -> None:
        super().watch_scroll_y(old, new)
        threshold = 0.001
        if (new <= threshold) and (old is None or old > threshold) and self.do_watching:
            self.do_watching = False
            self.post_message(self.ScrolledToTop(self))

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
        self.file_size = message.size
        self.hash = message.hash

    def compose(self):
        align = "right" if self.me else "left"
        with CondManage(self.me, Right):
            yield Label(f"{self.nickname} {self.time}", id="meta", classes=f"meta {align}")
        with CondManage(self.me, Right):
            if self.type == StealthIM.apis.message.MessageType.Text.value:
                yield Markdown(self.text, id="message", classes=f"msg")
            elif self.type == StealthIM.apis.message.MessageType.File.value:
                with Container(id="file-box"):
                    yield Label(self.text, id="file-name")
                    yield Label(self.file_size, id="file-size")
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

    async def on_key(self, event: events.Key) -> None:
        if event.key in ("enter", "space"):
            self.post_message(
                events.Click(
                    self,
                    self.region.x, self.region.y,
                    0, 0, 1, False, False, False)
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
    def on_changed(self, _event) -> None:
        self.selected = None


# noinspection PyProtectedMember
def add_global_hook(screen):
    if not hasattr(screen, "_popup_callback_click"):
        screen._popups = []

        # noinspection PyUnresolvedReferences,PyProtectedMember
        async def callback(_self, event: Click) -> None:
            for obj in screen._popups:
                await obj.on_global_click(event)

        screen._popup_callback_click = callback
        screen._decorated_handlers.setdefault(Click, [])
        screen._decorated_handlers[Click].append((callback, None))
    if not hasattr(screen, "_popup_callback_key"):
        screen._popups = []

        # noinspection PyUnresolvedReferences,PyProtectedMember
        async def callback(_self, event: Key) -> None:
            for obj in screen._popups:
                await obj.on_global_key(event)

        screen._popup_callback_key = callback
        screen._decorated_handlers.setdefault(Key, [])
        screen._decorated_handlers[Key].append((callback, None))


class AbstractPopup(Widget):
    def __init__(self, id):
        super().__init__(id=id)
        self._popup: Widget | None = None

    # noinspection PyProtectedMember
    @staticmethod
    def add_global_hook(screen):
        if not hasattr(screen, "_popups"):
            screen._popups = []
        if not hasattr(screen, "_popup_callback_click"):
            # noinspection PyUnresolvedReferences,PyProtectedMember
            async def callback(_self, event: Click) -> None:
                for obj in screen._popups[::]:
                    await obj.on_global_click(event)

            screen._popup_callback_click = callback
            screen._decorated_handlers.setdefault(Click, [])
            screen._decorated_handlers[Click].append((callback, None))
        if not hasattr(screen, "_popup_callback_key"):
            # noinspection PyUnresolvedReferences,PyProtectedMember
            async def callback(_self, event: Key) -> None:
                for obj in screen._popups[::]:
                    await obj.on_global_key(event)

            screen._popup_callback_key = callback
            screen._decorated_handlers.setdefault(Key, [])
            screen._decorated_handlers[Key].append((callback, None))

    def on_mount(self) -> None:
        add_global_hook(self.app.screen)
        # noinspection PyProtectedMember,PyUnresolvedReferences
        self.app.screen._popups.append(self)

    def on_unmount(self) -> None:
        # noinspection PyUnresolvedReferences,PyProtectedMember
        if hasattr(self.app.screen, "_popups") and self in self.app.screen._popups:
            self.app.screen._popups.remove(self)

    def compose(self) -> ComposeResult:
        yield from ()

    async def close_popup(self) -> None:
        if self._popup:
            await self._popup.remove()
            self._popup = None

    def on_global_click(self, event: Key) -> None:
        raise NotImplementedError

    def on_global_key(self, event: Key) -> None:
        raise NotImplementedError

    async def show_popup(self, *args, **kwargs) -> None:
        raise NotImplementedError


class CommonPopup(AbstractPopup):
    def __init__(self, inner_widget: Container, position: str = "right", id: str | None = None) -> None:
        super().__init__(id=id)
        self.inner_widget = inner_widget
        self.position = position
        self.styles.width = "auto"
        self.styles.height = "auto"

    async def show_popup(self) -> None:
        await self.close_popup()
        popup_content = self.inner_widget
        self._popup = popup_content
        popup_content.styles.position = "absolute"
        popup_content.styles.layer = "overlay"
        popup_content.styles.dock = self.position
        await self.app.screen.mount(popup_content)

    async def on_global_click(self, event: events.Click) -> None:
        if self._popup and self._popup not in event.widget.ancestors:
            await self.close_popup()

    async def on_global_key(self, event: events.Key) -> None:
        if self._popup and event.key == "escape":
            await self.close_popup()


class Popup(CommonPopup):
    def __init__(self, inner_widget: Container, position: str = "right", id: str | None = None) -> None:
        super().__init__(inner_widget=inner_widget, position=position, id=id)
        self.styles.display = "none"

    async def close_popup(self) -> None:
        await super().close_popup()


class PopupPlane(CommonPopup):
    def __init__(self, text: str, inner_widget: Container, position: str = "right", id: str | None = None) -> None:
        super().__init__(inner_widget=inner_widget, position=position, id=id)
        self.label = FocusableLabel(text)

    def compose(self):
        yield self.label

    async def on_global_click(self, event: events.Click) -> None:
        await super().on_global_click(event)
        if not self._popup and event.widget == self.label:
            await self.show_popup()

    async def on_key(self, event: events.Key) -> None:
        if event.key in ("enter", "space"):
            await self.show_popup()


class PopupMenu(AbstractPopup):
    class Command(Message):
        def __init__(self, name: str, control) -> None:
            super().__init__()
            self.name = name
            self.self = control  # For Textual event routing

        @property
        def control(self) -> "PopupMenu":
            return self.self

    def __init__(self, text: str, *items: tuple[str, str], id: str | None = None) -> None:
        super().__init__(id=id)
        self._popup: ReactiveListView | None = None
        self.label = FocusableLabel(text)
        self.items = items
        self.styles.width = "auto"
        self.styles.height = "auto"

    def compose(self):
        yield self.label

    async def show_popup(self, event: events.Click) -> None:
        await self.close_popup()

        max_text_len = max(len(label) for label, _ in self.items)
        menu_width = max_text_len + 6
        menu_height = len(self.items) + 2

        menu = ReactiveListView(
            *[ListItem(Label(label), id=name) for label, name in self.items],
        )
        self._popup = menu

        menu.styles.border = ("round", "green")
        menu.styles.width = menu_width
        menu.styles.height = menu_height
        menu.styles.position = "absolute"
        menu.styles.layer = "overlay"
        menu.styles.offset = event.screen_x, event.screen_y

        self.watch(menu, "selected", self.on_selected)

        menu.focus()

        await self.app.screen.mount(menu)

    async def on_selected(self) -> None:
        if not self._popup or self._popup.index is None:
            return
        self.post_message(
            self.Command(self.items[self._popup.index][1], self)
        )
        await self.close_popup()

    async def on_global_click(self, event: events.Click) -> None:
        if event.widget == self.label or event.widget == self._popup:
            return
        if self._popup:
            await self.close_popup()

    @on(Click)
    async def on_click(self, event: events.Click) -> None:
        if event.widget == self.label:
            await self.show_popup(event)

    async def on_global_key(self, event: events.Key) -> None:
        if event.key not in ("up", "down", "enter") and self._popup:
            await self.close_popup()
