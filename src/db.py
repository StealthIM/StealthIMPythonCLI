import datetime
import os
from typing import cast, Optional

from sqlalchemy import Column, Integer, String, create_engine, DateTime, Text, func
from sqlalchemy.orm import declarative_base, sessionmaker

import StealthIM
import codes
from StealthIM.apis.message import MessageType

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), "../data/configs.sqlite"))
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)

Base = declarative_base()
engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, future=True)
SessionLocal = sessionmaker(bind=engine)

MAX_MSGID = 2 ** 63 - 1


class Server(Base):
    __tablename__ = "servers"
    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    url = Column(String, nullable=False)


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(Integer, nullable=False)
    username = Column(String, nullable=False)
    session = Column(String, nullable=False)


class Group(Base):
    __tablename__ = "groups"
    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(Integer, nullable=False)
    group_id = Column(Integer, nullable=False)
    name = Column(String, nullable=False)
    last_update = Column(DateTime, nullable=False, default=datetime.datetime.now(datetime.timezone.utc))


class Message(Base):
    __tablename__ = "messages"
    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(Integer, nullable=False)
    group_id = Column(Integer, nullable=False)
    type = Column(Integer, nullable=False)
    msgid = Column(Integer, nullable=False)
    msg = Column(Text, nullable=False)
    time = Column(DateTime, nullable=False)
    username = Column(String, nullable=False)
    hash = Column(String, nullable=False)


class Nickname(Base):
    __tablename__ = "nicknames"
    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(Integer, nullable=False)
    username = Column(String, nullable=False)
    nickname = Column(String, nullable=False)
    last_update = Column(DateTime, nullable=False, default=datetime.datetime.now(datetime.timezone.utc))


class FileHash(Base):
    __tablename__ = "file_hashes"
    id = Column(Integer, primary_key=True, autoincrement=True)
    server_id = Column(Integer, nullable=False)
    group_id = Column(Integer, nullable=False)
    hash = Column(String, nullable=False)
    size = Column(Integer, nullable=False)


Base.metadata.create_all(bind=engine)


def load_servers_from_db() -> list[Server]:
    with SessionLocal() as session:
        return cast(list[Server], session.query(Server).all())


def get_server_from_db(url: str) -> Optional[Server]:
    with SessionLocal() as session:
        return session.query(Server).filter_by(url=url).first()


def save_server_to_db(name: str, url: str) -> None:
    with SessionLocal() as session:
        server = Server(name=name, url=url)
        session.add(server)
        session.commit()


def delete_server_from_db(server_id: int) -> None:
    with SessionLocal() as session:
        server = session.query(Server).filter_by(id=server_id).first()
        if server:
            session.delete(server)
            session.commit()


def load_users_from_db(server_id: int) -> list[User]:
    with SessionLocal() as session:
        return cast(list[User], session.query(User).filter_by(server_id=server_id).all())


def save_user_to_db(server_id: int, username: str, session_str: str) -> None:
    with SessionLocal() as session:
        user = User(server_id=server_id, username=username, session=session_str)
        session.add(user)
        session.commit()


def get_user_from_db(user_id: int) -> Optional[User]:
    with SessionLocal() as session:
        return session.query(User).filter_by(id=user_id).first()


def delete_user_from_db(user_id: int) -> None:
    with SessionLocal() as session:
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            session.delete(user)
            session.commit()


def update_user_session(user_id: int, new_session: str) -> None:
    with SessionLocal() as session:
        user = session.query(User).filter_by(id=user_id).first()
        if user:
            user.session = new_session
            session.commit()


def add_group(server_id: int, group_id: int, name: str) -> None:
    with SessionLocal() as session:
        group = Group(server_id=server_id, group_id=group_id, name=name,
                      last_update=datetime.datetime.now(datetime.timezone.utc)
                      )
        session.add(group)
        session.commit()


def update_group_name(group_id: int, server_id: int, new_name: str) -> None:
    with SessionLocal() as session:
        group = session.query(Group).filter_by(group_id=group_id, server_id=server_id).first()
        if group:
            group.name = new_name
            group.last_update = datetime.datetime.now(datetime.timezone.utc)
            session.commit()


def get_group_msgid(group_id: int, server_id: int, latest: bool = True) -> Optional[int]:
    if latest:
        data = get_messages(server_id, group_id, MAX_MSGID, False, 1)
        if data:
            return cast(int, data[0].msgid)
        return 1
    else:
        data = get_messages(server_id, group_id, 0, True, 1)
        if data:
            return cast(int, data[0].msgid)
        return MAX_MSGID


async def get_group_name(server_id: int, user: StealthIM.User, group_id: int, force_flush=False) -> StealthIM.group.GroupPublicInfoResult:
    with SessionLocal() as session:
        group = session.query(Group).filter_by(group_id=group_id, server_id=server_id).first()
    if not group or datetime.datetime.now(datetime.timezone.utc) - group.last_update.replace(
            tzinfo=datetime.timezone.utc) > datetime.timedelta(days=1) or force_flush:
        res = await StealthIM.Group(user, group_id).get_info()
        if res.result.code == codes.SUCCESS:
            if group:
                update_group_name(group_id, server_id, res.name)
            else:
                add_group(server_id, group_id, res.name)
        return res
    return StealthIM.group.GroupPublicInfoResult(
        result=StealthIM.apis.common.Result(
            code=codes.SUCCESS,
            msg=""
        ),
        create_at="0",
        name=str(group.name),
    )


def add_nickname(server_id: int, username: str, nickname: str) -> None:
    with SessionLocal() as session:
        col = Nickname(server_id=server_id, username=username, nickname=nickname,
                       last_update=datetime.datetime.now(datetime.timezone.utc))
        session.add(col)
        session.commit()


def update_nickname(server_id: int, username: str, nickname: str) -> None:
    with SessionLocal() as session:
        col = session.query(Nickname).filter_by(username=username, server_id=server_id).first()
        if col:
            col.nickname = nickname
            col.last_update = datetime.datetime.now(datetime.timezone.utc)
            session.commit()


async def get_nickname(server_id: int, user: StealthIM.User, username: str) -> StealthIM.user.UserPublicInfo:
    with SessionLocal() as session:
        col = session.query(Nickname).filter_by(server_id=server_id, username=username).first()
    if not col or datetime.datetime.now(datetime.timezone.utc) - col.last_update.replace(
            tzinfo=datetime.timezone.utc) > datetime.timedelta(days=1):
        res = await user.get_user_info(username)
        if res.result.code == codes.SUCCESS:
            if col:
                update_nickname(server_id, username, res.nickname)
            else:
                add_nickname(server_id, username, res.nickname)
        return res
    return StealthIM.group.StealthIM.user.UserPublicInfo(
        result=StealthIM.apis.common.Result(
            code=codes.SUCCESS,
            msg=""
        ),
        nickname=str(col.nickname),
    )


def add_message(
        server_id: int,
        group_id: int,
        type_: int,
        msg: str,
        time: datetime.datetime,
        username: str,
        msgid: int,
        hash_: str = ""
):
    with SessionLocal() as session:
        msg = Message(
            server_id=server_id,
            group_id=group_id,
            type=type_,
            msg=msg,
            time=time,
            username=username,
            hash=hash_,
            msgid=msgid
        )
        session.add(msg)
        session.commit()
        msg = session.query(Message).filter_by(server_id=server_id, group_id=group_id, msgid=msgid).first()
        return msg


def recall_message(
        server_id: int,
        group_id: int,
        msgid: int,
):
    with SessionLocal() as session:
        msg = session.query(Message).filter_by(server_id=server_id, group_id=group_id, msgid=msgid).first()
        if not msg:
            return
        msg.type = MessageType.Recall
        msg.msg = ""
        session.add(msg)
        session.commit()


def get_latest_messages(
        server_id: int,
        group_id: int,
        limit: int = 100
) -> list[Message]:
    with SessionLocal() as session:
        max_id = session.query(func.max(Message.msgid)).filter_by(
            server_id=server_id, group_id=group_id
        ).scalar() or 0
    return get_messages(server_id, group_id, max_id + 1, False, limit)


def get_messages(
        server_id: int,
        group_id: int,
        from_: int,
        old_to_new: bool = True,
        limit: int = 100
) -> list[Message]:
    with SessionLocal() as session:
        if old_to_new:
            # 从 from_ 往新的方向
            base_query = (
                session.query(Message)
                .filter(
                    Message.server_id == server_id,
                    Message.group_id == group_id,
                    Message.msgid > from_
                )
                .order_by(Message.msgid.asc())
            )
        else:
            # 从 from_ 往旧的方向
            base_query = (
                session.query(Message)
                .filter(
                    Message.server_id == server_id,
                    Message.group_id == group_id,
                    Message.msgid < from_
                )
                .order_by(Message.msgid.desc())
            )

        subquery = base_query.limit(limit).subquery()

        return cast(list[Message],
                    session.query(Message)
                    .from_statement(subquery.select().order_by(subquery.c.msgid.asc()))
                    .all()
                    )


def add_file_size(server_id: int, group_id: int, hash_: str, size: int) -> None:
    with SessionLocal() as session:
        count = session.query(FileHash).count()
        if count >= 1000:
            # 删除最旧的项
            oldest = session.query(FileHash).order_by(FileHash.id.asc()).limit(count - 999).all()
            for item in oldest:
                session.delete(item)
        file_hash = FileHash(server_id=server_id, group_id=group_id, hash=hash_, size=size)
        session.add(file_hash)
        session.commit()


async def get_file_size(group: StealthIM.Group, hash_str: str) -> int:
    server_id = cast(int, get_server_from_db(group.user.server.url).id)
    with SessionLocal() as session:
        res = session.query(FileHash).filter_by(server_id=server_id, group_id=group.group_id, hash=hash_str).first()
        if res:
            return cast(int, res.size)

        size_res = await group.get_file_info(hash_str)
        if size_res.result.code == codes.SUCCESS:
            add_file_size(server_id, group.group_id, hash_str, size_res.size)
            return size_res.size
        return 0

