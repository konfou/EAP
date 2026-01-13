from typing import Callable

from fastapi import Header, HTTPException, status

ROLE_RANK = {
    "reader": 0,
    "operator": 1,
    "admin": 2,
}


def get_role(x_role: str | None = Header(default="reader", alias="X-Role")) -> str:
    role = (x_role or "reader").strip().lower()
    if role not in ROLE_RANK:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid role",
        )
    return role


def require_role(required_role: str) -> Callable[[str], str]:
    def _check(role: str = Header(default="reader", alias="X-Role")) -> str:
        normalized = (role or "reader").strip().lower()
        if normalized not in ROLE_RANK:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid role",
            )
        if ROLE_RANK[normalized] < ROLE_RANK[required_role]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role",
            )
        return normalized

    return _check
