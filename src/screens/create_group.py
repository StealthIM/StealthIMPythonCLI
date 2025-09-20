import asyncio
from typing import Optional

import StealthIM
import codes

from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label

from patch import ModalScreen

class CreateGroupScreen(ModalScreen):
    SCREEN_NAME = "CreateGroup"
    CSS_PATH = "../../styles/create_group.tcss"

    def __init__(self):
        super().__init__()
        self.group_name: Optional[Input] = None
        self.is_creating = False

    def compose(self) -> ComposeResult:
        with Vertical(id="create-container"):
            self.group_name = Input(placeholder="Group Name", id="create-group-name")
            yield self.group_name
            with Horizontal():
                yield Button("Back", id="back")
                yield Button("Create", id="create", variant="success")
            yield Label("", id="status")

    @on(Button.Pressed, "#back")
    async def on_back(self, _event) -> None:
        self.dismiss(False)

    @work()
    @on(Button.Pressed, "#create")
    async def on_create(self, _event) -> None:
        if self.is_creating:
            return
        group_name = (self.group_name.value or "").strip()
        status = self.query_one("#status", Label)
        if not group_name:
            status.update("[red]Please enter group name[/]")
            return
        status.update("[yellow]Creating group, please wait...[/]")
        self.is_creating = True
        try:
            res = await StealthIM.Group.create(self.app.data.user, group_name)
            if res.result.code != codes.SUCCESS:
                status.update(f"[red]Create failed: {res.result.code}({codes.get_msg(res.result.code)}): {res.result.msg}[/]")
                self.is_creating = False
                return
        except Exception as e:
            status.update(f"[red]Create failed: {e}[/]")
            self.is_creating = False
            return
        self.is_creating = False
        status.update("[green]Group created successfully![/]")
        await asyncio.sleep(1)
        self.dismiss(True)

