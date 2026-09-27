from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from .database import get_db
from . import models


def get_current_user(request: Request, db: Session = Depends(get_db)) -> models.User | None:
    """
    Resolves the logged-in user from the signed session cookie ONLY.
    Never trust a user id passed in the query string or body for
    'who am I' -- that is exactly the IDOR pattern T2 is designed to catch.
    """
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(models.User, user_id)


def require_user(user: models.User | None = Depends(get_current_user)) -> models.User:
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_role(*roles: str):
    def _dep(user: models.User = Depends(require_user)) -> models.User:
        if user.role not in roles:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user
    return _dep


# Convenience role dependencies
require_participant = require_role("participant")
require_judge = require_role("judge")
require_organizer = require_role("organizer", "admin")
require_admin = require_role("admin")
