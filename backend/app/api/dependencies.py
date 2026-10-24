from fastapi import Request
from sqlalchemy import text


def generation_session(request: Request):
    # No transaction/connection is acquired until persistence after generation.
    with request.app.state.sessions() as db:
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise

def session(request: Request):
    # SQLite write transactions serialize state checks and decisions atomically.
    with request.app.state.sessions() as db:
        db.execute(text("BEGIN IMMEDIATE"))
        try:
            yield db
            db.commit()
        except Exception:
            db.rollback()
            raise

def read_session(request: Request):
    # Read-only handlers do not need BEGIN IMMEDIATE or a write transaction.
    with request.app.state.sessions() as db:
        yield db
