from textual import events, on
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


class PopupMenu(Widget):
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
        if not self._menu or self._menu.index is None:
            return
        self.post_message(
            self.Command(self.items[self._menu.index][1], self)
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

    def on_mount(self) -> None:
        add_global_hook(self.app.screen)
        # noinspection PyProtectedMember,PyUnresolvedReferences
        self.app.screen._popups.append(self)

    def on_unmount(self) -> None:
        # noinspection PyUnresolvedReferences,PyProtectedMember
        if hasattr(self.app.screen, "_popups") and self in self.app.screen._popups:
            self.app.screen._popups.remove(self)


class PopupPlane(Widget):
    def __init__(self, text: str, inner_widget: Container, position: str = "right", id: str | None = None) -> None:
        super().__init__(id=id)
        self.label = FocusableLabel(text)
        self._popup: Widget | None = None
        self.styles.width = "auto"
        self.styles.height = "auto"
        self.inner_widget = inner_widget
        self.position = position

    def compose(self):
        yield self.label

    async def show_popup(self, _event: events.Click | events.Key) -> None:
        await self.close_popup()
        popup_content = self.inner_widget
        self._popup = popup_content
        popup_content.styles.position = "absolute"
        popup_content.styles.layer = "overlay"
        popup_content.styles.dock = self.position
        await self.app.screen.mount(popup_content)
        # for child in popup_content.children:
        #     if child.focusable:
        #         child.focus()
        #         break

    async def close_popup(self) -> None:
        if self._popup:
            await self._popup.remove()
            self._popup = None

    async def on_global_click(self, event: events.Click) -> None:
        if event.widget == self.label:
            await self.show_popup(event)
        elif self._popup and not (event.widget == self._popup or (hasattr(event.widget, 'ancestors') and self._popup in event.widget.ancestors)):
            await self.close_popup()

    async def on_key(self, event: events.Key) -> None:
        if event.key in ("enter", "space"):
            await self.show_popup(event)

    async def on_global_key(self, event: events.Key) -> None:
        if event.key == "escape" and self._popup:
            await self.close_popup()

    def on_mount(self) -> None:
        add_global_hook(self.app.screen)
        # noinspection PyUnresolvedReferences,PyProtectedMember
        self.app.screen._popups.append(self)

    def on_unmount(self) -> None:
        # noinspection PyUnresolvedReferences,PyProtectedMember
        if hasattr(self.app.screen, "_popups") and self in self.app.screen._popups:
            self.app.screen._popups.remove(self)
