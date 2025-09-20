import asyncio
import datetime
from typing import Optional

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, Right, VerticalScroll
from textual.events import Key, Event
from textual.reactive import reactive
from textual.widgets import Button, Label, ListView, ListItem, TextArea
from textual.worker import Worker

import StealthIM
import codes
import db
from patch import Screen
from .common import MessageData
from .join_group import JoinGroupScreen
from .create_group import CreateGroupScreen
from .widgets import TopDetectingScroll, ScrolledToTop, ChatMessage, Popup


class ChatScreen(Screen):
    SCREEN_NAME = "Chat"
    CSS_PATH = "../../styles/chat.tcss"

    LIMIT = 100

    _push: reactive[bool] = reactive(True)

    def __init__(self):
        super().__init__()
        self.groups_list: Optional[ListView] = None
        self.groups: list[int] = []
        self.last_group: Optional[int] = None
        self.group: Optional[StealthIM.Group] = None
        self.message_worker: Optional[Worker] = None

    def compose(self) -> ComposeResult:
        yield Label(f"Server: {self.app.data.server_db.name}  User: {self.app.data.user_db.username}")

        with Horizontal(id="main"):
            # Left group list
            with Vertical(id="groups"):
                with Horizontal(id="group_bar"):
                    yield Label("Groups")
                    with Right():
                        yield Popup(
                            "+",
                            ("Join Group", "join_group"),
                            ("Create Group", "create_group"),
                        )
                self.groups_list = ListView(id="groups_list")
                yield self.groups_list

            # Right chat area
            with Vertical(id="chat"):
                with Horizontal(id="group-header"):
                    yield Label("", id="chat-title")
                    yield Label("...", id="group-menu")

                # Message area (scrollable)
                with TopDetectingScroll(id="messages"):
                    ...

                # Input area
                with Vertical(id="input-area"):
                    yield TextArea(id="msg-input")
                    with Right(id="tools"):
                        yield Button("Send", id="send")
        yield Label("", id="status")

    # Events

    # Update group lists when loading this page
    async def on_mount(self, _event: Event) -> None:
        self.flush_groups()

    @on(Popup.Command)
    async def on_command(self, event: Popup.Command) -> None:
        self.log(f"Command: {event.name}")
        if event.name == "join_group":
            await self.join_group()
        elif event.name == "create_group":
            await self.create_group()

    # Reload the messages when select another group
    @work()
    @on(ListView.Selected, "#groups_list")
    async def on_change_group(self, event: ListView.Selected) -> None:
        group_id = self.groups[event.index]
        if group_id == self.last_group:
            # The group is not changed
            return
        if self.message_worker:
            # Stop the last message worker
            self.message_worker.cancel()

        self.last_group = group_id
        self.group = StealthIM.Group(self.app.data.user, group_id)
        self.app.data.group = self.group

        await self.update_chat_title(group_id)
        # Reset the scroll
        messages = self.query_one("#messages", TopDetectingScroll)
        messages.reset_watching()
        messages.remove_children()

        # First load messages from db
        msgs = db.get_latest_messages(self.app.data.server_db.id, group_id, limit=self.LIMIT)
        for msg in msgs:
            message = self.build_msg_from_db(msg)
            await self.add_message(messages, message)
        messages.scroll_end()

        # Then start the message worker to receive
        self.message_worker = self.get_messages(messages)

    # Load more messages when scrolled to top
    @work()
    async def on_scrolled_to_top(self, _event: ScrolledToTop):
        messages = self.query_one("#messages", TopDetectingScroll)
        if not messages.children:
            return
        new_messages = db.get_messages(
            self.app.data.server_db.id,
            self.group.group_id,
            from_=messages.children[0].msgid,
            old_to_new=False,
            limit=self.LIMIT
        )

        distance_to_bottom = messages.max_scroll_y - messages.scroll_offset.y
        for msg in new_messages[::-1]:
            message = self.build_msg_from_db(msg)
            await self.add_message(messages, message, bottom=False)

            new_offset = messages.max_scroll_y - distance_to_bottom
            messages.scroll_to(y=new_offset, animate=False)

        if len(new_messages) == self.LIMIT:
            # Has more data, watch for next event
            messages.reset_watching()

    # Catch the Ctrl+Enter on the input
    async def on_key(self, event: Key) -> None:
        if event.key == "ctrl+j":
            focused = self.focused  # 当前聚焦控件
            if isinstance(focused, TextArea) and focused.id == "msg-input":
                self.do_send()

    # The send button
    @on(Button.Pressed, "#send")
    async def on_send(self, _event: Event) -> None:
        self.do_send()

    # Helper functions

    # Add a message in the scroll
    async def add_message(self, scroll: VerticalScroll, message: MessageData, bottom=True):
        sender_res = await db.get_nickname(self.app.data.server_db.id, self.app.data.user, message.username)
        if sender_res.result.code != codes.SUCCESS:
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

    async def get_group_members(self, group):
        res = await group.get_members()
        if res.result.code != codes.SUCCESS:
            members = "?"
        else:
            members = str(len(res.members))
        return members

    async def get_group_name(self, group):
        res = await db.get_group_name(self.app.data.server_db.id, self.app.data.user, group.group_id)
        if res.result.code != codes.SUCCESS:
            group_name = "未知"
        else:
            group_name = res.name
        return group_name

    async def update_chat_title(self, group_id):
        chat_title = self.query_one("#chat-title", Label)
        res = await db.get_group_name(self.app.data.server_db.id, self.app.data.user, group_id)
        if res.result.code != codes.SUCCESS:
            chat_title.update("未知")
        else:
            chat_title.update(res.name)

    def build_msg_from_db(self, msg: db.Message):
        return MessageData(
            group_id=msg.group_id,
            server_id=msg.server_id,
            msg=msg.msg,
            type=msg.type,
            time=msg.time,
            username=msg.username,
            msgid=msg.msgid,
            hash=msg.hash,
        )

    async def join_group(self):
        if await self.app.push_screen_wait(JoinGroupScreen.SCREEN_NAME):
            self.flush_groups()

    async def create_group(self):
        if await self.app.push_screen_wait(CreateGroupScreen.SCREEN_NAME):
            self.flush_groups()


    # Workers

    # Update the groups
    @work()
    async def flush_groups(self) -> None:
        if self.groups_list is None:
            # The UI is not ready
            return

        if self.message_worker:
            # Stop the message worker
            self.message_worker.cancel()

        status = self.query_one("#status", Label)

        # Get all the groups
        res = await self.app.data.user.get_groups()
        if res.result.code != codes.SUCCESS:
            status.update(
                f"[red]无法更新群组: {res.result.code}({codes.get_msg(res.result.code)}): {res.result.msg}[/]")
            return

        await self.groups_list.clear()
        self.groups = res.groups
        for group_id in res.groups:
            group = StealthIM.Group(self.app.data.user, group_id)

            group_name = await self.get_group_name(group)
            members = await self.get_group_members(group)

            await self.groups_list.append(ListItem(Label(f"{group_id}. {group_name} ({members})")))

    # Send the message in the input
    @work()
    async def do_send(self):
        text_area = self.query_one("#msg-input", TextArea)
        text = text_area.text
        text_area.text = ""
        if not self.group:
            return
        await self.group.send_text(text)
        messages = self.query_one("#messages", TopDetectingScroll)
        messages.scroll_end()

    # The actual worker to update the group list
    @work()
    async def get_messages(self, messages: VerticalScroll) -> None:
        server_id = self.app.data.server_db.id
        group_id = self.group.group_id

        while True:
            latest_msgid = db.get_group_msgid(group_id, server_id)
            try:
                gen = self.group.receive_text(from_id=latest_msgid)
                async for message in gen:
                    msg = db.add_message(
                        server_id, group_id, message.type.value,
                        message.msg.replace("\n", "\n\n"),
                        datetime.datetime.fromtimestamp(int(message.time)), message.username,
                        message.msgid, message.hash
                    )
                    db.update_group_msgid(group_id, server_id, message.msgid)

                    await self.add_message(messages, self.build_msg_from_db(msg))
            except RuntimeError:
                pass
            except asyncio.CancelledError:
                break
