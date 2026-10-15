"""Fail-closed authorization of short-lived Next.js service-issued identity JWTs."""
from __future__ import annotations

import os
import re
from typing import Annotated

import jwt
from fastapi import Depends, Header, HTTPException

_SUBJECT = re.compile(r"^github:[0-9]{1,30}$")
_ISSUER = "quantedge-next"
_AUDIENCE = "quantedge-api"

def require_subject(authorization: Annotated[str | None, Header()] = None) -> str:
    secret = os.getenv("QUANTEDGE_API_JWT_SECRET", "")
    if len(secret) < 32:
        raise HTTPException(status_code=503, detail="Authenticated research is not configured")
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Authentication required",
                            headers={"WWW-Authenticate": "Bearer"})
    try:
        payload = jwt.decode(
            authorization.removeprefix("Bearer "), secret, algorithms=["HS256"],
            audience=_AUDIENCE, issuer=_ISSUER, leeway=5,
            options={"require": ["sub", "exp", "iat", "iss", "aud"]},
        )
        sub = payload["sub"]
        if not isinstance(sub, str) or not _SUBJECT.fullmatch(sub):
            raise ValueError("Invalid stable user identity")
        return sub
    except (jwt.PyJWTError, ValueError, KeyError, TypeError) as exc:
        raise HTTPException(status_code=401, detail="Invalid or expired authentication",
                            headers={"WWW-Authenticate": "Bearer"}) from exc

OwnerId = Annotated[str, Depends(require_subject)]
