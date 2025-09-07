import dataclasses
import datetime
from contextlib import AbstractContextManager, nullcontext
from typing import Optional


class CondManage(AbstractContextManager):
    def __init__(self, do: bool, klass, *args, **kwargs):
        self._enabled = do
        if do:
            self._ctx = klass(*args, **kwargs)
        else:
            self._ctx = nullcontext()

    def __enter__(self):
        return self._ctx.__enter__()

    def __exit__(self, exc_type, exc_value, traceback):
        return self._ctx.__exit__(exc_type, exc_value, traceback)


@dataclasses.dataclass()
class MessageData:
    server_id: int
    group_id: int
    type: int
    msgid: int
    msg: str
    time: datetime.datetime
    username: str
    hash: str
    nickname: Optional[str] = None


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
