from typing import Optional
import StealthIM
import codes
from textual import on, work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Input, Label, Select
from patch import ModalScreen


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
        if not group_id_str:
            status.update("[red]Please enter group ID[/]")
            return
        if not group_id_str.isdigit():
            status.update("[red]Please enter a valid group ID[/]")
            return
        status.update("[yellow]Joining group, please wait...[/]")
        self.is_joining = True
        try:
            res = await StealthIM.Group(self.app.data.user, int(group_id_str)).join(password)
            if res.result.code == codes.SUCCESS:
                status.update("[green]Joined group successfully![/]")
                self.dismiss(True)
            else:
                status.update(f"[red]Failed: {codes.get_msg(res.result.code)} ({res.result.msg})[/]")
        except Exception as e:
            status.update(f"[red]Error: {e}[/]")
        finally:
            self.is_joining = False


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
            if res.result.code == codes.SUCCESS:
                status.update("[green]Group created successfully![/]")
                self.dismiss(True)
            else:
                status.update(f"[red]Failed: {codes.get_msg(res.result.code)} ({res.result.msg})[/]")
        except Exception as e:
            status.update(f"[red]Error: {e}[/]")
        finally:
            self.is_creating = False


class ModifyGroupNameScreen(ModalScreen[bool]):
    SCREEN_NAME = "ModifyGroupName"
    CSS_PATH = "../../styles/modify_group_name.tcss"

    def __init__(self, group: Optional[StealthIM.Group] = None):
        super().__init__()
        self.group = group
        self.group_name: Optional[Input] = None
        self.is_modifying = False

    def compose(self) -> ComposeResult:
        with Vertical(id="modify-name-container"):
            self.group_name = Input(placeholder="New Group Name", id="modify-group-name")
            yield self.group_name
            with Horizontal():
                yield Button("Back", id="back")
                yield Button("Confirm", id="confirm", variant="success")

    @on(Button.Pressed, "#back")
    async def on_back(self, _event) -> None:
        self.dismiss(False)

    @work()
    @on(Button.Pressed, "#confirm")
    async def on_confirm(self, _event) -> None:
        if self.is_modifying:
            return
        new_name = (self.group_name.value or "").strip()
        if not new_name:
            self.notify("Please enter new group name")
            return
        self.is_modifying = True
        res = await self.group.change_name(new_name)
        if res.result.code == codes.SUCCESS:
            self.notify("Group name updated!")
            self.dismiss(True)
        else:
            if res.result.code == codes.GROUP_USER_PERMISSION_DENIED:
                self.notify(f"Modify group name failed: Permission Denied")
            else:

                self.notify(f"Name failed: {codes.get_msg(res.result.code)} ({res.result.msg})")
        self.is_modifying = False


class ModifyGroupPasswordScreen(ModalScreen):
    SCREEN_NAME = "ModifyGroupPassword"
    CSS_PATH = "../../styles/modify_group_password.tcss"

    def __init__(self, group: Optional[StealthIM.Group] = None):
        super().__init__()
        self.group = group
        self.group_password: Optional[Input] = None
        self.is_modifying = False

    def compose(self) -> ComposeResult:
        with Vertical(id="modify-password-container"):
            self.group_password = Input(placeholder="New Password", id="modify-group-password")
            yield self.group_password
            with Horizontal():
                yield Button("Back", id="back")
                yield Button("Confirm", id="confirm", variant="success")

    @on(Button.Pressed, "#back")
    async def on_back(self, _event) -> None:
        self.dismiss(False)

    @work()
    @on(Button.Pressed, "#confirm")
    async def on_confirm(self, _event) -> None:
        if self.is_modifying:
            return
        new_password = (self.group_password.value or "").strip()
        if not new_password:
            self.notify("Please enter new password")
            return
        self.is_modifying = True
        res = await self.group.change_password(new_password)
        if res.result.code == codes.SUCCESS:
            self.notify("Password updated!")
            self.dismiss()
        else:
            if res.result.code == codes.GROUP_USER_PERMISSION_DENIED:
                self.notify(f"Modify group name failed: Permission Denied")
            else:

                self.notify(f"Name failed: {codes.get_msg(res.result.code)} ({res.result.msg})")
        self.is_modifying = False


class InviteMemberScreen(ModalScreen):
    SCREEN_NAME = "InviteMember"
    CSS_PATH = "../../styles/invite_member.tcss"

    def __init__(self, group: Optional[StealthIM.Group] = None):
        super().__init__()
        self.group = group
        self.username: Optional[Input] = None
        self.is_inviting = False

    def compose(self) -> ComposeResult:
        with Vertical(id="invite-member-container"):
            self.username = Input(placeholder="Username to invite", id="invite-member-username")
            yield self.username
            with Horizontal():
                yield Button("Back", id="back")
                yield Button("Invite", id="invite", variant="success")

    @on(Button.Pressed, "#back")
    async def on_back(self, _event) -> None:
        self.dismiss(False)

    @work()
    @on(Button.Pressed, "#invite")
    async def on_invite(self, _event) -> None:
        if self.is_inviting:
            return
        username = (self.username.value or "").strip()
        if not username:
            self.notify("Please enter username to invite")
            return
        self.is_inviting = True
        res = await self.group.invite(username)
        if res.result.code == codes.SUCCESS:
            self.notify("Invitation sent!")
            self.dismiss(True)
        elif res.result.code == codes.GROUP_USER_PERMISSION_DENIED:
            self.notify(f"No permission to invite: {codes.get_msg(res.result.code)} ({res.result.msg})")
        elif res.result.code == codes.USER_NOT_FOUND:
            self.notify(f"User not found: {codes.get_msg(res.result.code)} ({res.result.msg})")
        else:
            self.notify(f"Invite failed: {codes.get_msg(res.result.code)} ({res.result.msg})")
        self.is_inviting = False


class SetMemberScreen(ModalScreen):
    SCREEN_NAME = "SetMember"
    CSS_PATH = "../../styles/set_member.tcss"

    def __init__(self, group: StealthIM.Group, username: str):
        super().__init__()
        self.group = group
        self.username = username
        self.role_label: Optional[Select] = None
        self.is_setting = False
        
    def compose(self) -> ComposeResult:
        with Vertical(id="set-member-container"):
            self.role_label = Select(
                options=[
                    ("Set as Manager", "manager"),
                    ("Set as Member", "member")
                ],
                prompt="Select Role",
                id="set-member-action"
            )
            yield self.role_label
            with Horizontal(id="set-member-btns"):
                yield Button("Cancel", id="back")
                yield Button("Kick", id="kick", variant="error")
                yield Button("Confirm", id="confirm", variant="success")

    @on(Button.Pressed, "#back")
    async def on_back(self, _event) -> None:
        self.dismiss(False)

    @work()
    @on(Button.Pressed, "#confirm")
    async def on_confirm(self, _event) -> None:
        if self.is_setting:
            return

        action = self.role_label.value
        username = self.username
        
        if action == Select.BLANK:
            self.notify("Please select an role")
            return 

        self.is_setting = True

        if action == "member":
            role = StealthIM.group.GroupMemberType.Member
        elif action == "manager":
            role = StealthIM.group.GroupMemberType.Manager
        else:
            assert False, "Invalid action"

        res = await self.group.set_member_role(username, role)
        if res.result.code == codes.SUCCESS:
            self.notify("Set role success!")
            self.dismiss(True)
        elif res.result.code == codes.GROUP_USER_PERMISSION_DENIED:
            self.notify("No permission to set role.")
        elif res.result.code == codes.USER_NOT_FOUND:
            self.notify("User not found.")
        else:
            self.notify(f"Set role failed: {codes.get_msg(res.result.code)} ({res.result.msg})")

        self.is_setting = False

    @work()
    @on(Button.Pressed, "#kick")
    async def on_kick(self, _event) -> None:
        if self.is_setting:
            return

        username = self.username
        self.is_setting = True

        res = await self.group.kick(username)
        if res.result.code == codes.SUCCESS:
            self.notify("Kick member success!")
            self.dismiss(True)
        elif res.result.code == codes.GROUP_USER_PERMISSION_DENIED:
            self.notify("No permission to kick member.")
        elif res.result.code == codes.USER_NOT_FOUND:
            self.notify("User not found.")
        else:
            self.notify(f"Kick member failed: {codes.get_msg(res.result.code)} ({res.result.msg})")

        self.is_setting = False
