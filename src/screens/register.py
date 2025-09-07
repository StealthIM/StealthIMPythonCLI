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
            username = (self.query_one("#username", Input).value or "").strip()
            password = (self.query_one("#password", Input).value or "").strip()
            confirm_password = (self.query_one("#confirm-password", Input).value or "").strip()
            nickname = (self.query_one("#nickname", Input).value or "").strip()
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
            self.app.call_after_refresh(lambda: asyncio.create_task(
                self.do_register(username, password, nickname)
            ))

    async def do_register(self, username, password, nickname) -> None:
        status = self.query_one("#status", Label)
        try:
            res = await self.app.data.server.register(username, password, nickname)
            if res.result.code != 800:
                status.update(
                    f"[red]注册失败: {res.result.code}({codes.get_msg(res.result.code)}): {res.result.msg}[/]"
                )
                return
        except Exception as e:
            status.update(f"[red]注册失败: {e}[/]")
            return
        status.update("[green]注册成功！请返回登录。[/]")
