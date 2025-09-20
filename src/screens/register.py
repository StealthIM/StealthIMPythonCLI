import asyncio
import codes

from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Button, Input, Label

from patch import ModalScreen


class RegisterScreen(ModalScreen):
    SCREEN_NAME = "Register"
    CSS_PATH = "../../styles/register.tcss"

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Vertical(id="register-container"):
            yield Input(placeholder="Username", id="username")
            yield Input(placeholder="Password", password=True, id="password")
            yield Input(placeholder="Confirm Password", password=True, id="confirm-password")
            yield Input(placeholder="Nickname", password=False, id="nickname")
            with Horizontal():
                yield Button("Back", id="back")
                yield Button("Register", id="register", variant="success")
            yield Label("", id="status")
        yield Footer()

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "back":
            await self.app.pop_screen()
        elif event.button.id == "register":
            username = (self.query_one("#username", Input).value or "").strip()
            password = (self.query_one("#password", Input).value or "").strip()
            confirm_password = (self.query_one("#confirm-password", Input).value or "").strip()
            nickname = (self.query_one("#nickname", Input).value or "").strip()
            status = self.query_one("#status", Label)

            if not username or not password or not confirm_password:
                status.update("[red]Please enter username and password[/]")
                return
            if password != confirm_password:
                status.update("[red]Passwords do not match[/]")
                return
            if not 3 <= len(username) <= 20:
                status.update("[red]Username length must be between 3 and 20 characters[/]")
                return
            if not all(c.isalnum() or c == '_' for c in username):
                status.update("[red]Username can only contain letters, numbers, and underscores[/]")
                return
            if not 6 <= len(password) <= 20:
                status.update("[red]Password length must be between 6 and 20 characters[/]")
                return
            status.update("[yellow]Registering, please wait...[/]")
            self.app.call_after_refresh(lambda: asyncio.create_task(
                self.do_register(username, password, nickname)
            ))

    async def do_register(self, username, password, nickname) -> None:
        status = self.query_one("#status", Label)
        try:
            res = await self.app.data.server.register(username, password, nickname)
            if res.result.code != codes.SUCCESS:
                status.update(
                    f"[red]Registration failed: {res.result.code}({codes.get_msg(res.result.code)}): {res.result.msg}[/]"
                )
                return
        except Exception as e:
            status.update(f"[red]Registration failed: {e}[/]")
            return
        status.update("[green]Registration successful! Please return to login.[/]")
