import asyncio
import datetime
from typing import Optional

import StealthIM
import db
import codes

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, Right, VerticalScroll
from textual.events import Key, Event
from textual.reactive import reactive
from textual.widgets import Header, Footer, Button, Label, ListView, ListItem, TextArea
from textual.worker import Worker

from patch import Screen
from log import logger
from .common import MessageData
from .widgets import TopDetectingScroll, ScrolledToTop, ChatMessage


class ChatScreen(Screen):
    SCREEN_NAME = "Chat"
    CSS_PATH = "../../styles/chat.tcss"

    _push: reactive[bool] = reactive(True)

    def __init__(self):
        super().__init__()
        self.groups_list: Optional[ListView] = None
        self.groups: list[int] = []
        self.last_group: Optional[int] = None
        self.group: Optional[StealthIM.Group] = None
        self.message_worker: Optional[Worker] = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Label(f"服务器: {self.app.data.server_db.name}  用户: {self.app.data.user_db.username}")

        with Horizontal(id="main"):
            # 左侧群组列表
            with Vertical(id="groups"):
                yield Label("群组")
                self.groups_list = ListView(id="groups_list")
                yield self.groups_list

            # 右侧聊天区
            with Vertical(id="chat"):
                with Horizontal(id="group-header"):
                    yield Label("", id="chat-title")
                    yield Label("...", id="group-menu")

                # 消息区（可滚动）
                with TopDetectingScroll(id="messages"):
                    ...

                # 输入区
                with Vertical(id="input-area"):
                    yield TextArea(id="msg-input")
                    with Right(id="tools"):
                        yield Button("发送", id="send")
            yield Label("", id="status")

    async def on_mount(self, value: int) -> None:
        self.run_worker(self.update_groups())

    async def update_groups(self):
        logger.debug("Start")
        if self.groups_list is None:
            logger.debug("Failed to update")
            return
        status = self.query_one("#status", Label)
        res = await self.app.data.user.get_groups()
        if res.result.code != 800:
            status.update(
                f"[red]无法更新群组: {res.result.code}({codes.get_msg(res.result.code)}): {res.result.msg}[/]")
            return
        await self.groups_list.clear()
        self.groups = res.groups
        for group_id in res.groups:
            group = StealthIM.Group(self.app.data.user, group_id)
            res = await db.get_group_name(self.app.data.server_db.id, self.app.data.user, group_id)
            if res.result.code != 800:
                group_name = "未知"
            else:
                group_name = res.name

            res = await group.get_members()
            if res.result.code != 800:
                members = "?"
            else:
                members = str(len(res.members))

            await self.groups_list.append(ListItem(Label(f"{group_id}. {group_name} ({members})")))

    @work()
    @on(ListView.Selected, "#groups_list")
    async def on_change_group(self, event: ListView.Selected) -> None:
        idx = event.index
        group_id = self.groups[idx]
        if group_id == self.last_group:
            return
        if self.message_worker:
            self.message_worker.cancel()

        self.last_group = group_id
        self.group = StealthIM.Group(self.app.data.user, group_id)
        self.app.data.group = self.group
        logger.debug(f"Change to group: {group_id}")

        chat_title = self.query_one("#chat-title", Label)
        res = await db.get_group_name(self.app.data.server_db.id, self.app.data.user, group_id)
        if res.result.code != 800:
            chat_title.update("未知")
        else:
            chat_title.update(res.name)

        messages = self.query_one("#messages", TopDetectingScroll)
        messages.reset_watching()
        messages.remove_children()

        # First load from db
        msgs = db.get_latest_messages(self.app.data.server_db.id, group_id, limit=5)
        if msgs:
            for msg in msgs:
                message = MessageData(
                    group_id=msg.group_id,
                    server_id=msg.server_id,
                    msg=msg.msg,
                    type=msg.type,
                    time=msg.time,
                    username=msg.username,
                    msgid=msg.msgid,
                    hash=msg.hash,
                )
                await self.add_message(messages, message)
            messages.scroll_end()

        self.message_worker = self.get_messages(messages)

    async def add_message(self, scroll: VerticalScroll, message: MessageData, bottom=True):
        sender_res = await db.get_nickname(self.app.data.server_db.id, self.app.data.user, message.username)
        if sender_res.result.code != 800:
            message.nickname = "未知"
        else:
            message.nickname = sender_res.nickname
        if bottom:
            attr = {"after": -1}
        else:
            attr = {"before": 0}
        await scroll.mount(
            ChatMessage(message, self.app.data.user_db),
            **attr
        )

    @work()
    async def on_scrolled_to_top(self, event: ScrolledToTop):
        messages = self.query_one("#messages", TopDetectingScroll)
        latest_message: ChatMessage = messages.children[0]
        latest_msgid = latest_message.msgid
        more_messages = db.get_messages(
            self.app.data.server_db.id,
            self.group.group_id,
            from_=latest_msgid,
            old_to_new=False,
            limit=5
        )
        distance_to_bottom = messages.max_scroll_y - messages.scroll_offset.y
        for msg in more_messages[::-1]:
            message = MessageData(
                group_id=msg.group_id,
                server_id=msg.server_id,
                msg=msg.msg,
                type=msg.type,
                time=msg.time,
                username=msg.username,
                msgid=msg.msgid,
                hash=msg.hash,
            )
            await self.add_message(messages, message, bottom=False)
            new_offset = messages.max_scroll_y - distance_to_bottom
            messages.scroll_to(y=new_offset, animate=False)
        if len(more_messages) == 5:
            # Has more
            messages.reset_watching()

    async def on_key(self, event: Key) -> None:
        """全局键盘监听，只在 TextArea 聚焦时处理 Ctrl+Enter"""
        if event.key == "ctrl+j":
            focused = self.focused  # 当前聚焦控件
            if isinstance(focused, TextArea) and focused.id == "msg-input":
                self.do_send()

    @on(Button.Pressed, "#send")
    async def on_send(self, event: Event) -> None:
        self.do_send()

    @work()
    async def do_send(self):
        text_area = self.query_one("#msg-input", TextArea)
        text = text_area.text
        logger.debug(f"Send: {text}")
        text_area.text = ""
        await self.group.send_text(text)
        messages = self.query_one("#messages", TopDetectingScroll)
        messages.scroll_end()

    @work()
    async def get_messages(self, messages: VerticalScroll) -> None:
        server_id = self.app.data.server_db.id
        group_id = self.group.group_id
        while True:
            latest_msgid = db.get_group_msgid(group_id, server_id)
            try:
                gen = self.group.receive_text(from_id=latest_msgid)
                async for message in gen:
                    message.msg = message.msg.replace("\n", "\n\n")
                    time = datetime.datetime.fromtimestamp(int(message.time))
                    sender_res = await db.get_nickname(server_id, self.app.data.user, message.username)
                    if sender_res.result.code != 800:
                        sender = "未知"
                    else:
                        sender = sender_res.nickname
                    if messages.scroll_offset.y >= messages.max_scroll_y:
                        is_bottom = True
                    else:
                        is_bottom = False
                    db.add_message(server_id, group_id, message.type.value, message.msg, time, message.username,
                                         message.msgid, message.hash)
                    db.update_group_msgid(group_id, server_id, message.msgid)
                    await self.add_message(messages, MessageData(
                        group_id=group_id,
                        server_id=server_id,
                        msg=message.msg,
                        type=message.type.value,
                        time=time,
                        username=message.username,
                        msgid=message.msgid,
                        hash=message.hash,
                    ))
                    if is_bottom:
                        messages.scroll_end()
            except RuntimeError:
                pass
            except asyncio.CancelledError:
                break
