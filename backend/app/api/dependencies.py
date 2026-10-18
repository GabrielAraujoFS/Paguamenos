from fastapi import Request
from sqlalchemy import text

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
