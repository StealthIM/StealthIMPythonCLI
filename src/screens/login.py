import asyncio
import StealthIM
import db

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Button, Input, Label, ListView, ListItem

from patch import Screen, ModalScreen
from .common import LoginUserScreenReturn
from log import logger


class LoginScreen(Screen):
    SCREEN_NAME = "Login"

    def __init__(self):
        super().__init__()
        self.users = []
        self.user_list: ListView | None = None
        self.logging = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Label(f"服务器: {self.app.data.server_db.name}", id="server-label")
        self.users = db.load_users_from_db(self.app.data.server_db.id)
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
        from .login import LoginNewUserScreen
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
        from .register import RegisterScreen
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
            from .login import ReLoginScreen
            res = await self.app.push_screen_wait(ReLoginScreen(user.username))
            if res.user_cancelled:
                return
            db.update_user_session(user.id, res.session)
            user = db.get_user_from_db(user.id)
            self.app.data.user_db = user
            self.app.data.user = StealthIM.User(self.app.data.server, user.session)

        from .chat import ChatScreen
        await self.app.push_screen(ChatScreen())
        self.logging = False


class ReLoginScreen(ModalScreen[LoginUserScreenReturn]):
    SCREEN_NAME = "ReLogin"
    CSS_PATH = ["../../styles/login_new_user.tcss", "../../styles/relogin.tcss"]

    def __init__(self, username: str) -> None:
        super().__init__()
        self.username = username
        self.password: Input | None = None
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
        self.dismiss(LoginUserScreenReturn(user_cancelled=True))

    @work()
    @on(Button.Pressed, "#login")
    async def on_button_pressed(self, _event: Button.Pressed) -> None:
        if self.is_logging:
            return
        username = self.username
        password = (self.password.value or "").strip()
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
        self.dismiss(LoginUserScreenReturn(
            user_cancelled=False,
            username=username,
            session=res.session,
        ))
        self.is_logging = False


class LoginNewUserScreen(ModalScreen[LoginUserScreenReturn]):
    SCREEN_NAME = "LoginNewUser"
    CSS_PATH = "../../styles/login_new_user.tcss"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.is_logging = False
        self.username: Input | None = None
        self.password: Input | None = None

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
        self.dismiss(LoginUserScreenReturn(user_cancelled=True))

    @work()
    @on(Button.Pressed, "#login")
    async def on_button_pressed(self, _event: Button.Pressed) -> None:
        if self.is_logging:
            return
        username = (self.username.value or "").strip()
        password = (self.password.value or "").strip()
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
        self.dismiss(LoginUserScreenReturn(
            user_cancelled=False,
            username=username,
            session=res.session,
        ))
        self.is_logging = False
