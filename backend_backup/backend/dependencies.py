from fastapi import Depends, HTTPException, status
from backend.auth import decode_jwt  # Adjust import if decode function resides elsewhere

def get_current_user(token: str = Depends(lambda: None)):
    """Placeholder dependency to extract JWT payload.
    In the real app replace the lambda with the actual token extraction (e.g., OAuth2PasswordBearer).
    """
    if not token:
        return {}
    return decode_jwt(token)

def logistics_user(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "logistics":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient permissions")
    return current_user
