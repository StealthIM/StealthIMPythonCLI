import asyncio
from typing import Optional

import StealthIM
import codes
import db

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Button, Input, Label, ListView, ListItem

from StealthIM import Group
from patch import Screen, ModalScreen
from log import logger


class JoinGroupScreen(ModalScreen):
    SCREEN_NAME = "JoinGroup"
    CSS_PATH = "../../styles/join_group.tcss"

    def __init__(self):
        super().__init__()
        self.password: Optional[Input] = None
        self.group_id: Optional[Input] = None
        self.is_joining = False

    def compose(self) -> ComposeResult:
        with Vertical(id="join-container"):
            self.group_id = Input(placeholder="Group ID", id="join-group-id")
            self.password = Input(placeholder="Password", id="join-password")
            yield self.group_id
            yield self.password
            with Horizontal():
                yield Button("Back", id="back")
                yield Button("Join", id="join", variant="success")
            yield Label("", id="status")

    @on(Button.Pressed, "#back")
    async def on_back(self, _event) -> None:
        self.dismiss(False)

    @work()
    @on(Button.Pressed, "#join")
    async def on_join(self, _event) -> None:
        if self.is_joining:
            return
        group_id_str = (self.group_id.value or "").strip()
        password = (self.password.value or "").strip()
        status = self.query_one("#status", Label)
        if not group_id_str or not password:
            status.update("[red]Please enter group ID and password[/]")
            return
        if not group_id_str.isdigit():
            status.update("[red]Please enter a valid group ID[/]")
            return
        group_id = int(group_id_str)
        if group_id.bit_count() > 64:
            status.update("[red]Please enter a valid group ID[/]")
            return
        status.update("[yellow]Joining, please wait...[/]")
        self.is_joining = True

        group = Group(self.app.data.user, group_id)
        res = await group.join(password)
        if res.result.code != codes.SUCCESS:
            status.update(f"[red]Join failed: {res.result.code}({codes.get_msg(res.result.code)}): {res.result.msg}[/]")
            self.is_joining = False
            return
        self.is_joining = False
        self.dismiss(True)
