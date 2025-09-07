import asyncio
import dataclasses
import datetime
from typing import Optional

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Vertical, Horizontal, Grid, VerticalScroll, Right
from textual.events import Event, Key
from textual.reactive import reactive
from textual.widgets import Header, Footer, Button, Input, Static, ListView, ListItem, Label, Markdown, TextArea
from textual.worker import Worker

import StealthIM
import codes
import db
from log import logger
from patch import Screen, ModalScreen


@dataclasses.dataclass
class AddServerScreenReturn:
    user_cancelled: bool
    name: Optional[str] = None
    url: Optional[str] = None

@dataclasses.dataclass
class LoginUserScreenReturn:
    user_cancelled: bool
    username: Optional[str] = None
    session: Optional[str] = None

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
    def __init__(self, text: str, sender: str, time: str, msgid: int, me: bool = False):
        super().__init__(classes='me' if me else 'other')
        self.text = text
        self.sender = sender
        self.me = me
        self.time = time
        self.msgid = msgid

    def compose(self) -> ComposeResult:
        # 顶部一行：发送者 + 时间
        align = "right" if self.me else "left"
        if self.me:
            with Right():
                yield Label(f"{self.sender} {self.time}", id="meta", classes=f"meta {align}")
            with Right():
                yield Markdown(self.text, id="message", classes=f"msg {'me' if self.me else 'other'}")
        else:
            yield Label(f"{self.sender} {self.time}", id="meta", classes=f"meta {align}")
            yield Markdown(self.text, id="message", classes=f"msg {'me' if self.me else 'other'}")
        # 消息体（markdown渲染）


class ServerSelectScreen(Screen):
    SCREEN_NAME = "ServerSelect"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.servers = db.load_servers_from_db()
        self.server_list: Optional[ListView] = None

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static("请选择一个服务器: ")
        self.server_list = ListView(
            *[ListItem(Label(f"{srv.name} - {srv.url}")) for srv in self.servers]
        )
        yield self.server_list
        with Horizontal():
            yield Button("添加服务器", id="add")
            yield Button("删除服务器", id="delete")
            yield Button("进入", id="enter")

        yield Label("", id="status")
        yield Footer()

    @on(Button.Pressed, "#delete")
    async def on_delete(self, _event: Button.Pressed) -> None:
        if not self.server_list or not self.servers:
            return
        idx = self.server_list.index
        if idx is not None and 0 <= idx < len(self.servers):
            server = self.servers[idx]
            db.delete_server_from_db(server.id)
            self.servers.pop(idx)
            await self.server_list.remove_items([idx])

    @on(Button.Pressed, "#enter")
    async def on_login(self, _event: Button.Pressed) -> None:
        if not self.server_list or not self.servers:
            return
        idx = self.server_list.index
        if idx is not None and 0 <= idx < len(self.servers):
            server = self.servers[idx]
            self.app.data.server = StealthIM.Server(server.url)
            self.app.data.server_db = server
            await self.app.push_screen(LoginScreen.SCREEN_NAME)

    @work
    @on(Button.Pressed, "#add")
    async def on_add(self, _event: Button.Pressed) -> None:
        status = self.query_one("#status", Label)
        ret = await self.app.push_screen_wait(AddServerScreen.SCREEN_NAME)
        if not (ret and not ret.user_cancelled and ret.name and ret.url):
            return
        if not await StealthIM.Server(ret.url).ping():
            status.update("[red]服务器不可达[/]")
            return
        db.save_server_to_db(ret.name, ret.url)
        self.servers = db.load_servers_from_db()

        if self.server_list is not None:
            await self.server_list.clear()
            await self.server_list.extend(
                [ListItem(Label(f"{srv.name} - {srv.url}")) for srv in self.servers]
            )


class AddServerScreen(ModalScreen[AddServerScreenReturn]):
    SCREEN_NAME = "AddServer"
    CSS_PATH = "../styles/add_server.tcss"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.name_input: Optional[Input] = None
        self.addr_input: Optional[Input] = None

    def compose(self) -> ComposeResult:
        yield Grid(
            Label("添加新服务器", id="title"),
            Label("服务器名称："),
            name_input := Input(placeholder="Server Name"),
            Label("服务器地址："),
            addr_input := Input(placeholder="example.com"),
            Button("确认添加", id="confirm"),
            Button("取消", id="cancel"),
            id="dialog"
        )
        self.name_input = name_input
        self.addr_input = addr_input

    @on(Button.Pressed, "#confirm")
    def on_confirm(self, _event: Button.Pressed) -> None:
        if not (self.name_input and self.addr_input):
            return
        name = self.name_input.value or ""
        address = self.addr_input.value or ""
        name = name.strip()
        address = address.strip()
        if name and address:
            self.dismiss(
                AddServerScreenReturn(
                    user_cancelled=False,
                    name=name,
                    url=address,
                )
            )

    @on(Button.Pressed, "#cancel")
    def on_cancel(self, _event: Button.Pressed) -> None:
        self.dismiss(AddServerScreenReturn(user_cancelled=True))


class LoginScreen(Screen):
    SCREEN_NAME = "Login"

    def __init__(self):
        super().__init__()
        self.users = db.load_users_from_db(self.app.data.server_db.id)
        self.user_list: Optional[ListView] = None
        self.logging = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Label(f"服务器: {self.app.data.server_db.name}", id="server-label")
        self.user_list = ListView(
            *[ListItem(Label(user.username)) for user in self.users]
        )
        yield self.user_list
        with Horizontal():
            yield Button("返回", id="back")
            yield Button("登录", id="login", variant="success")
            yield Button("登录新账号", id="login_new")
            yield Button("注册", id="register")
            yield Button("删除", id="remove")
        yield Label("", id="status")
        yield Footer()

    @on(Button.Pressed, "#back")
    async def on_back(self, _event: Button) -> None:
        await self.app.pop_screen()

    @work()
    @on(Button.Pressed, "#login_new")
    async def on_login_new(self, _event: Button) -> None:
        ret = await self.app.push_screen_wait(LoginNewUserScreen.SCREEN_NAME)
        if not (ret and not ret.user_cancelled and ret.username and ret.session):
            return
        db.save_user_to_db(
            server_id=self.app.data.server_db.id,
            username=ret.username,
            session_str=ret.session,
        )
        self.users = db.load_users_from_db(self.app.data.server_db.id)
        if self.user_list is not None:
            await self.user_list.clear()
            await self.user_list.extend(
                [ListItem(Label(user.username)) for user in self.users]
            )

    @on(Button.Pressed, "#remove")
    async def on_remove(self, _event: Button) -> None:
        if not self.user_list:
            return
        idx = self.user_list.index
        if (idx is None) or (not 0 <= idx < len(self.users)):
            return
        user = self.users[idx]
        db.delete_user_from_db(user.id)
        self.users.pop(idx)
        await self.user_list.remove_items([idx])

    @on(Button.Pressed, "#register")
    async def on_register(self, _event: Button) -> None:
        await self.app.push_screen(RegisterScreen.SCREEN_NAME)

    @work()
    @on(Button.Pressed, "#login")
    async def on_login(self, _event: Button) -> None:
        if not self.user_list or self.logging:
            return
        idx = self.user_list.index
        if (idx is None) or (not 0 <= idx < len(self.users)):
            return

        user = self.users[idx]
        self.logging = True

        self.app.data.user_db = user
        self.app.data.user = StealthIM.User(self.app.data.server, user.session)
        api_res = await self.app.data.user.get_self_info()
        if api_res.result.code == 1502:
            # The session is out of date
            res = await self.app.push_screen_wait(ReLoginScreen(user.username))
            if res.user_cancelled:
                return
            db.update_user_session(user.id, res.session)
            user = db.get_user_from_db(user.id)
            self.app.data.user_db = user
            self.app.data.user = StealthIM.User(self.app.data.server, user.session)
        await self.app.push_screen(ChatScreen())
        self.logging = False


class ReLoginScreen(ModalScreen[LoginUserScreenReturn]):
    SCREEN_NAME = "ReLogin"
    CSS_PATH = ["../styles/login_new_user.tcss", "../styles/relogin.tcss"]

    def __init__(self, username: str) -> None:
        super().__init__()
        self.username = username
        self.password: Optional[Input] = None
        self.is_logging = False

    def compose(self) -> ComposeResult:
        with Vertical(id="login-container"):
            yield Label("登录已过期. 请重新登录: ")
            self.password = Input(placeholder="密码", id="password", password=True)
            yield self.password
            with Horizontal():
                yield Button("返回", id="back")
                yield Button("登录", id="login", variant="success")
            yield Label("", id="status")

    @on(Button.Pressed, "#back")
    async def on_back(self, _event: Button) -> None:
        self.dismiss(
            LoginUserScreenReturn(
                user_cancelled=True,
            )
        )

    @work()
    @on(Button.Pressed, "#login")
    async def on_button_pressed(self, _event: Button.Pressed) -> None:
        if self.is_logging:
            return
        username = self.username
        password = self.password.value or ""
        username = username.strip()
        password = password.strip()
        status = self.query_one("#status", Label)
        if not password:
            status.update("[red]请输入密码[/]")
            return
        status.update("[yellow]正在登录，请稍候...[/]")
        self.is_logging = True

        try:
            res = await self.app.data.server.login(username, password)
            self.is_logging = False
            if not res:
                status.update("[red]登录失败，请检查密码[/]")
                return
        except Exception as e:
            self.app.data.user = None
            status.update(f"[red]登录失败: {e}[/]")
            self.is_logging = False
            return
        status.update("[green]登录成功！[/]")
        await asyncio.sleep(1)
        self.dismiss(
            LoginUserScreenReturn(
                user_cancelled=False,
                username=username,
                session=res.session,
            )
        )
        self.is_logging = False


class LoginNewUserScreen(ModalScreen[LoginUserScreenReturn]):
    SCREEN_NAME = "LoginNewUser"
    CSS_PATH = "../styles/login_new_user.tcss"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_logging = False
        self.username: Optional[Input] = None
        self.password: Optional[Input] = None

    def compose(self) -> ComposeResult:
        with Vertical(id="login-container"):
            self.username = Input(placeholder="用户名", id="username")
            self.password = Input(placeholder="密码", id="password", password=True)
            yield self.username
            yield self.password
            with Horizontal():
                yield Button("返回", id="back")
                yield Button("登录", id="login", variant="success")
            yield Label("", id="status")

    @on(Button.Pressed, "#back")
    async def on_back(self, _event: Button) -> None:
        self.dismiss(
            LoginUserScreenReturn(
                user_cancelled=True,
            )
        )

    @work()
    @on(Button.Pressed, "#login")
    async def on_button_pressed(self, _event: Button.Pressed) -> None:
        if self.is_logging:
            return
        username = self.username.value or ""
        password = self.password.value or ""
        username = username.strip()
        password = password.strip()
        status = self.query_one("#status", Label)
        if not username or not password:
            status.update("[red]请输入用户名和密码[/]")
            return
        status.update("[yellow]正在登录，请稍候...[/]")
        self.is_logging = True

        try:
            res = await self.app.data.server.login(username, password)
            self.is_logging = False
            if not res:
                status.update("[red]登录失败，请检查用户名和密码[/]")
                return
        except Exception as e:
            self.app.data.user = None
            status.update(f"[red]登录失败: {e}[/]")
            self.is_logging = False
            return
        status.update("[green]登录成功！[/]")
        await asyncio.sleep(1)
        self.dismiss(
            LoginUserScreenReturn(
                user_cancelled=False,
                username=username,
                session=res.session,
            )
        )
        self.is_logging = False


class RegisterScreen(ModalScreen):
    SCREEN_NAME = "Register"
    CSS_PATH = "../styles/register.tcss"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="register-container"):
            yield Input(placeholder="用户名", id="username")
            yield Input(placeholder="密码", password=True, id="password")
            yield Input(placeholder="确认密码", password=True, id="confirm-password")
            yield Input(placeholder="昵称", password=False, id="nickname")
            with Horizontal():
                yield Button("返回", id="back")
                yield Button("注册", id="register", variant="success")
            yield Label("", id="status")
        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            await self.app.pop_screen()
        elif event.button.id == "register":
            username = self.query_one("#username", Input).value or ""
            password = self.query_one("#password", Input).value or ""
            confirm_password = self.query_one("#confirm-password", Input).value or ""
            nickname = self.query_one("#nickname", Input).value or ""
            username = username.strip()
            password = password.strip()
            confirm_password = confirm_password.strip()
            nickname = nickname.strip()
            status = self.query_one("#status", Label)

            if not username or not password or not confirm_password:
                status.update("[red]请输入用户名和密码[/]")
                return
            if password != confirm_password:
                status.update("[red]两次输入的密码不一致[/]")
                return
            if not 3 <= len(username) <= 20:
                status.update("[red]用户名长度应在3到20个字符之间[/]")
                return
            if not all(c.isalnum() or c == '_' for c in username):
                status.update("[red]用户名只能包含字母、数字、下划线[/]")
                return
            if not 6 <= len(password) <= 20:
                status.update("[red]密码长度应在6到20个字符之间[/]")
                return
            status.update("[yellow]正在注册，请稍候...[/]")
            self.app.call_after_refresh(lambda: asyncio.create_task(self.do_register(username, password, nickname)))

    async def do_register(self, username, password, nickname) -> None:
        status = self.query_one("#status", Label)
        try:
            res = await self.app.data.server.register(username, password, nickname)
            if res.result.code != 800:
                status.update(
                    f"[red]注册失败: {res.result.code}({codes.get_msg(res.result.code)}): {res.result.msg}[/]")
                return
        except Exception as e:
            status.update(f"[red]注册失败: {e}[/]")
            return
        status.update("[green]注册成功！请返回登录。[/]")


class ChatScreen(Screen):
    SCREEN_NAME = "Chat"
    CSS_PATH = "../styles/chat.tcss"

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
            status.update(f"[red]无法更新群组: {res.result.code}({codes.get_msg(res.result.code)}): {res.result.msg}[/]")
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
                await self.add_message(messages, msg)
            messages.scroll_end()

        self.message_worker = self.get_messages(messages)

    async def add_message(self, messages, msg, bottom=True):
        sender_res = await db.get_nickname(self.app.data.server_db.id, self.app.data.user, msg.username)
        if sender_res.result.code != 800:
            sender = "未知"
        else:
            sender = sender_res.nickname
        if bottom:
            attr = {"after": -1}
        else:
            attr = {"before": 0}
        await messages.mount(
            ChatMessage(
                text=msg.msg,
                sender=sender,
                time=msg.time.strftime('%Y-%m-%d %H:%M:%S'),
                me=msg.username == self.app.data.user_db.username,
                msgid=msg.msgid
            ),
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
            await self.add_message(messages, msg, bottom=False)
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
                    await messages.mount(
                        ChatMessage(
                            text=message.msg,
                            sender=sender,
                            time=time.strftime('%Y-%m-%d %H:%M:%S'),
                            me= message.username==self.app.data.user_db.username,
                            msgid=int(message.msgid)
                        ),
                        after=-1
                    )
                    if is_bottom:
                        messages.scroll_end()
                    db.add_message(server_id, group_id, message.type.value, message.msg, time, message.username, message.msgid, message.hash)
                    db.update_group_msgid(group_id, server_id, message.msgid)
            except RuntimeError:
                pass
            except asyncio.CancelledError:
                break
