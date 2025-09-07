from textual import on
from textual.containers import VerticalScroll, Right
from textual.events import Event
from textual.reactive import reactive
from textual.widgets import Label, Markdown, Static

import StealthIM
import db
from .common import CondManage, MessageData


class ScrolledToTop(Event):
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
