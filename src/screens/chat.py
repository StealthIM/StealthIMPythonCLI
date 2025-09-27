import asyncio
import datetime
import math
from typing import Optional, cast

import platformdirs
from textual import events, on, work
from textual.app import ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Right, Vertical, VerticalScroll
from textual.events import Click, Event, Key
from textual.widgets import Button, Checkbox, Footer, Label, ListItem, ListView, TextArea
from textual.worker import Worker

import StealthIM
import codes
import db
import log
import tools
from StealthIM.apis.message import MessageType
from patch import Screen, Container
from .common import MessageData
from .group_manage import InviteMemberScreen, JoinGroupScreen, CreateGroupScreen, ModifyGroupNameScreen, \
    ModifyGroupPasswordScreen, SetMemberScreen
from .widgets import ChatMessage, FocusableLabel, Popup, PopupMenu, PopupPlane, TopDetectingScroll


class GroupManagerContainer(Container):
    DEFAULT_CSS = """
    GroupManagerContainer {
        width: 0.4fr;
        padding: 1 2;
        border: round grey;
        background: $panel;
    }
    #member-bar {
        height: 1;
    }
    #member-list {
        height: 10;
    }
    .auto-height {
        height: auto;
    }
    .border {
        border: round grey;
        height: auto;
    }
    .auto-width {
        width: auto;
    }
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.parent: ChatScreen  # type: ignore[assignment]
        self.users = []

    def compose(self) -> ComposeResult:
        with VerticalScroll():
            with Container(classes="border"):
                with Horizontal(classes="auto-height"):
                    yield Label("ID: ")
                    yield Label("", id="group-id-value")
                with Horizontal(classes="auto-height"):
                    yield Label("Name: ")
                    yield Label("", id="group-name-value")
                    with Right():
                        yield FocusableLabel("Change", id="change-name", classes="link")
                with Horizontal(classes="auto-height"):
                    yield Label("Password (won't show)")
                    with Right():
                        yield FocusableLabel("Change", id="change-password", classes="link")
            with Vertical(classes="border"):
                with Horizontal(id="member-bar"):
                    yield Label("Members: ")
                    yield Label("", id="member-count")
                    with Right():
                        with Horizontal(classes="auto-width"):
                            yield FocusableLabel("Set as", id="set-member")
                            yield FocusableLabel("Invite", id="invite-member", variant="success")
                yield ListView(id="member-list")

    @work()
    async def on_mount(self, _event) -> None:
        group_id_label = self.query_one("#group-id-value", Label)
        group_name_label = self.query_one("#group-name-value", Label)
        group_members_count = self.query_one("#member-count", Label)
        group_members_list = self.query_one("#member-list", ListView)

        # Reset all values
        group_name_label.update("Loading...")
        group_members_list.clear()
        group_members_list.append(ListItem(Label("Loading...")))
        group_members_count.update("")

        group_id_label.update(str(self.app.data.group.group_id))

        self.flush_name()

        self.flush_group_members()

    @work()
    async def flush_name(self):
        group_name_label = self.query_one("#group-name-value", Label)
        name_res = await db.get_group_name(
            self.app.data.server_db.id,
            self.app.data.user,
            self.app.data.group.group_id
        )
        if name_res.result.code != codes.SUCCESS:
            group_name_label.update("Unknown")
            self.notify(
                f"[red]{name_res.result.code} ({codes.get_msg(name_res.result.code)}): {name_res.result.msg}[/])",
                title="Failed to get group name",
                severity="error",
            )
        else:
            group_name_label.update(name_res.name)

    @work()
    async def flush_group_members(self):
        group_members_count = self.query_one("#member-count", Label)
        group_members_list = self.query_one("#member-list", ListView)
        members_res = await self.app.data.group.get_members()
        if members_res.result.code != codes.SUCCESS:
            await group_members_list.clear()
            await group_members_list.append(ListItem(Label("Failed")))
            self.notify(
                f"[red]{members_res.result.code} ({codes.get_msg(members_res.result.code)}): {members_res.result.msg}[/])",
                title="Failed to get group members",
                severity="error",
            )
        else:
            await group_members_list.clear()
            group_members_count.update(str(len(members_res.members)))
            self.users = [member.name for member in members_res.members]
            for member in members_res.members:
                role = member.type.name
                nickname_res = await db.get_nickname(
                    self.app.data.server_db.id,
                    self.app.data.user,
                    member.name
                )
                if nickname_res.result.code != codes.SUCCESS:
                    name = member.name
                else:
                    name = f"{nickname_res.nickname} ({member.name})"
                group_members_list.append(ListItem(Label(f"{name} - {role}")))

    @on(Click, "#change-name")
    async def on_modify_group_info(self, _event) -> None:
        res = await self.app.push_screen_wait(ModifyGroupNameScreen(self.app.data.group))
        if res:
            await db.get_group_name(
                self.app.data.server_db.id,
                self.app.data.user,
                self.app.data.group.group_id,
                True
            )
            self.flush_name()
            self.parent.flush_groups()

    @on(Click, "#change-password")
    async def on_modify_group_password(self, _event) -> None:
        await self.app.push_screen(ModifyGroupPasswordScreen(self.app.data.group))

    @on(Click, "#invite-member")
    async def on_invite_member(self, _event) -> None:
        res = await self.app.push_screen_wait(InviteMemberScreen(self.app.data.group))
        if res:
            self.flush_group_members()
            self.parent.flush_groups()

    @on(Click, "#set-member")
    async def on_set_member(self, _event) -> None:
        member_list = self.query_one("#member-list", ListView)
        if member_list.index is None:
            self.notify("No member to set", title="Error", severity="error")
            return

        user = self.users[member_list.index]

        res = await self.app.push_screen_wait(SetMemberScreen(self.app.data.group, user))
        if res:
            self.flush_group_members()
            self.parent.flush_groups()


class MessageSelectContainer(Container):
    DEFAULT_CSS = """
    MessageSelectContainer {
        width: 25%;
        padding: 1 2;
        border: round grey;
        background: $panel;
    }
    #message-select {
        height: 7fr;
        border: solid gray;
        padding-top: 3;
        padding-right: 1;
    }
    #message-select-keys {
        height: 3fr;
    }
    """
    BINDINGS = [
        Binding("ctrl+z", "recall", "Recall", show=False),
        Binding("ctrl+d", "download", "Download", show=False),
    ]

    def __init__(self, message_list: VerticalScroll):
        super().__init__()
        self.message_count: Label | None = None
        self.checkbox_container: Container | None = None
        self.message_list = message_list
        self.last_int = None
        self.selected: list[ChatMessage] = []

    def compose(self) -> ComposeResult:
        with Horizontal():
            yield Label("Selected: ")
            yield (message_count := Label("0"))
            self.message_count = message_count
        yield (checkbox_container := Container(id="message-select"))
        with Vertical(id="message-select-keys"):
            yield Label("Keys:")
            yield Label("Ctrl+z: Recall")
            yield Label("Ctrl+d: Download file")
        self.checkbox_container = checkbox_container

    async def on_mount(self, event: events.Mount) -> None:
        await self.callback_scroll(0, 0)

    async def callback_scroll(self, _, new):
        rounded = round(new)
        if not math.isclose(new, rounded, abs_tol=1e-6) or self.last_int == rounded:
            return
        self.last_int = rounded

        if not self.is_mounted:
            return

        messages = cast(list[ChatMessage], self.visible_children(self.message_list))

        # 清空旧的 checkbox
        await self.checkbox_container.remove_children()

        # 根据可见消息重新生成 checkbox
        for msg in messages:
            # 计算相对 y 位置（消息的 virtual_region 是在 scroll 坐标系下的）
            y = int(msg.virtual_region.y - self.message_list.scroll_y)

            checkbox = Checkbox("Select", value=msg in self.selected)
            # 用 inline-style 定位 checkbox
            checkbox.styles.offset = (0, y)
            checkbox.styles.position = "absolute"
            checkbox.msg = msg

            await self.checkbox_container.mount(checkbox)

    @on(Checkbox.Changed)
    def on_check(self, event: Checkbox.Changed) -> None:
        checkbox = event.checkbox
        # noinspection PyUnresolvedReferences
        msg = checkbox.msg
        if event.value:
            self.selected.append(msg)
        else:
            self.selected.remove(msg)
        self.message_count.update(str(len(self.selected)))

    def action_recall(self):
        return

    async def action_download(self):
        if not (
            files := [msg for msg in self.selected if msg.type == MessageType.File.value]
        ):
            self.notify("No message to download", severity="error")
            return

        download_path = platformdirs.user_downloads_path()
        hashes = [msg.hash for msg in self.selected]
        filenames = [msg.text for msg in files]
        await self.app.data.group.download_files(hashes, filenames, download_path)

    @staticmethod
    def visible_children(scroll_container: VerticalScroll):
        return [
            child for child in scroll_container.children
            if scroll_container.window_region.contains_region(child.virtual_region)
        ]


class ChatScreen(Screen):
    SCREEN_NAME = "Chat"
    CSS_PATH = "../../styles/chat.tcss"

    LIMIT = 100

    BINDINGS = [("ctrl+s", "select_msg", "Select message")]

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
                        yield PopupMenu(
                            "+",
                            ("Join Group", "join_group"),
                            ("Create Group", "create_group"),
                            id="group-commands",
                        )
                self.groups_list = ListView(id="groups_list")
                yield self.groups_list

            # Right chat area
            with Vertical(id="chat"):
                with Horizontal(id="group-header"):
                    yield Label("", id="chat-title")
                    yield PopupPlane("...", id="group-menu", inner_widget=GroupManagerContainer())

                # Message area (scrollable)
                with TopDetectingScroll(id="messages"):
                    ...

                # Input area
                with Vertical(id="input-area"):
                    yield TextArea(id="msg-input")
                    with Right(id="tools"):
                        yield Button("Send", id="send")
        yield Label("", id="status")
        yield Footer()

    # Events

    # Update group lists when loading this page
    async def on_mount(self, _event: Event) -> None:
        group_menu = self.query_one("#group-menu", PopupPlane)
        group_menu.display = False
        self.flush_groups()

    @on(PopupMenu.Command, "#group-commands")
    async def on_group_menu_pressed(self, event: PopupMenu.Command) -> None:
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

        # Show the group setting button
        group_menu = self.query_one("#group-menu", PopupPlane)
        group_menu.display = True

        if self.message_worker:
            # Stop the last message worker
            self.message_worker.cancel()

        self.last_group = group_id
        self.group = StealthIM.Group(self.app.data.user, group_id)
        self.app.data.group = self.group

        await self.update_chat_title(group_id)
        # Reset the scroll
        messages = self.query_one("#messages", TopDetectingScroll)
        messages.remove_children()

        # First load messages from db
        msgs = db.get_latest_messages(self.app.data.server_db.id, group_id, limit=self.LIMIT)
        if msgs:
            for msg in msgs:
                message = self.build_msg_from_db(msg)
                await self.add_message(messages, message)
        else:
            # A new group, we only get the newest LIMIT messages
            # from_id=0, old_to_new=False means pull the latest messages
            gen = self.group.receive_text(from_id=0, old_to_new=False, sync=False, limit=self.LIMIT)
            msgs = [x async for x in gen][::-1]
            for msg in msgs:
                message = db.add_message(
                    self.app.data.server_db.id, self.group.group_id, msg.type.value,
                    msg.msg.replace("\n", "\n\n"),
                    datetime.datetime.fromtimestamp(int(msg.time)), msg.username,
                    msg.msgid, msg.hash
                )
                message = self.build_msg_from_db(message)
                await self.add_message(messages, message)

        messages.scroll_end()
        messages.reset_watching()

        # Then start the message worker to receive
        self.message_worker = self.get_messages(messages)

    # Load more messages when scrolled to top
    @work()
    @on(TopDetectingScroll.ScrolledToTop, "#messages")
    async def on_no_more_message(self, _event: TopDetectingScroll.ScrolledToTop):
        messages = self.query_one("#messages", TopDetectingScroll)
        if not messages.children:
            return

        # First get messages from database
        new_messages = db.get_messages(
            self.app.data.server_db.id,
            self.group.group_id,
            from_=messages.children[0].msgid,
            old_to_new=False,
            limit=self.LIMIT
        )
        if new_messages:
            distance_to_bottom = messages.max_scroll_y - messages.scroll_offset.y
            for msg in new_messages[::-1]:
                message = self.build_msg_from_db(msg)
                await self.add_message(messages, message, bottom=False)

                new_offset = messages.max_scroll_y - distance_to_bottom
                messages.scroll_to(y=new_offset, animate=False)
            messages.reset_watching()
        else:
            # There's no more messages in the database, try to pull from server
            oldest_msgid = db.get_group_msgid(self.group.group_id, self.app.data.server_db.id, False)
            gen = self.group.receive_text(from_id=oldest_msgid, old_to_new=False, sync=False, limit=self.LIMIT)
            msgs = [x async for x in gen][::-1]
            self.log(msgs)
            for msg in msgs:
                message = db.add_message(
                    self.app.data.server_db.id, self.group.group_id, msg.type.value,
                    msg.msg.replace("\n", "\n\n"),
                    datetime.datetime.fromtimestamp(int(msg.time)), msg.username,
                    msg.msgid, msg.hash
                )
                message = self.build_msg_from_db(message)
                await self.add_message(messages, message, bottom=False)
            if len(msgs) >= self.LIMIT:
                messages.reset_watching()

    # Catch the Ctrl+Enter on the input
    @on(Key)
    async def on_send_by_key(self, event: Key) -> None:
        if event.key == "ctrl+j":
            focused = self.focused  # 当前聚焦控件
            if isinstance(focused, TextArea) and focused.id == "msg-input":
                self.do_send()

    # The send button
    @on(Button.Pressed, "#send")
    async def on_send_by_btn(self, _event: Event) -> None:
        self.do_send()

    async def action_select_msg(self):
        if not self.group:
            self.notify("You need to select a group")
            return
        scroll = self.query_one("#messages", TopDetectingScroll)

        container = MessageSelectContainer(scroll)
        self.watch(scroll, "scroll_y", container.callback_scroll)
        popup = Popup(container, position="left")
        self.mount(popup)
        await popup.show_popup()

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

        if message.type == MessageType.File.value:
            file_res = await db.get_file_size(self.group, message.hash)
            message.size = tools.int2size(int(file_res))

        await scroll.mount(
            ChatMessage(message, self.app.data.user_db),
            **attr
        )

    async def recall_message(self, scroll: VerticalScroll):
        ...

    @staticmethod
    async def get_group_members(group):
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

    @staticmethod
    def build_msg_from_db(msg: db.Message):
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

                    if message.type != MessageType.Recall:
                        await self.add_message(messages, self.build_msg_from_db(msg))
                    else:
                        db.recall_message(server_id, group_id, message.msgid)
                        await self.recall_message(messages, message.msgid)
            except RuntimeError:
                pass
            except asyncio.CancelledError:
                break
