from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker
from sqlalchemy.pool import StaticPool

class Base(DeclarativeBase):
    pass

def make_engine(url: str):
    if not url.startswith("sqlite:"):
        raise ValueError("O MVP suporta apenas SQLite.")
    options = {"connect_args": {"check_same_thread": False, "timeout": 15}}
    if url in ("sqlite://", "sqlite:///:memory:"):
        options["poolclass"] = StaticPool
    engine = create_engine(url, **options)

    @event.listens_for(engine, "connect")
    def enable_foreign_keys(connection, _):
        connection.execute("PRAGMA foreign_keys=ON")
    return engine

def make_session_factory(engine):
    return sessionmaker(bind=engine, expire_on_commit=False)
