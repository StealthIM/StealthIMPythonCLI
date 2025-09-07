import StealthIM
import db

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Grid
from textual.widgets import Header, Footer, Button, Input, Static, ListView, ListItem, Label

from patch import Screen, ModalScreen
from .common import AddServerScreenReturn


class ServerSelectScreen(Screen):
    SCREEN_NAME = "ServerSelect"

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.servers = db.load_servers_from_db()
        self.server_list: ListView | None = None

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
            from .login import LoginScreen
            await self.app.push_screen(LoginScreen.SCREEN_NAME)

    @work
    @on(Button.Pressed, "#add")
    async def on_add(self, _event: Button.Pressed) -> None:
        status = self.query_one("#status", Label)
        from .server_select import AddServerScreen
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
        self.name_input: Input | None = None
        self.addr_input: Input | None = None

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
        name = self.name_input.value.strip()
        address = self.addr_input.value.strip()
        if name and address:
            self.dismiss(AddServerScreenReturn(
                user_cancelled=False,
                name=name,
                url=address,
            ))

    @on(Button.Pressed, "#cancel")
    def on_cancel(self, _event: Button.Pressed) -> None:
        self.dismiss(AddServerScreenReturn(user_cancelled=True))
