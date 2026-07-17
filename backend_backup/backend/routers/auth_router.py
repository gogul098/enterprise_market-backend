"""
Authentication router: /auth/signup and /auth/login
"""
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import User, Role, AuditLog, Vendor
from backend.schemas import SignupRequest, LoginRequest, AuthResponse
from backend.auth import hash_password, verify_password, create_access_token
from backend.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])

VALID_ROLES = {"Buyer", "Vendor", "Admin", "Logistics", "Warehouse"}


@router.post("/signup", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
def signup(payload: SignupRequest, db: Session = Depends(get_db)):
    """
    Register a new user.
    - Hashes password with bcrypt.
    - Assigns the role chosen by the user (Buyer, Vendor, or Admin).
    - Returns a JWT access token.
    """
    # Validate role
    if payload.role not in VALID_ROLES:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid role '{payload.role}'. Choose from: {', '.join(sorted(VALID_ROLES))}."
        )

    # Check if email already exists
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists."
        )

    # Create user
    user = User(
        email=payload.email,
        password_hash=hash_password(payload.password),
        address=payload.address if payload.role == "Buyer" else None
    )
    db.add(user)
    db.flush()  # Get user_id before role assignment

    # Assign chosen role
    chosen_role = db.query(Role).filter(Role.role_name == payload.role).first()
    if chosen_role:
        user.roles.append(chosen_role)

    # Sync Vendor table for AI Ecosystem
    if payload.role == "Vendor":
        vendor_entry = Vendor(
            vendor_id=str(user.user_id),
            vendor_name=payload.vendor_name or "Unknown Vendor",
            contact_email=payload.email,
            warehouse_count=0
        )
        db.add(vendor_entry)

    # Audit log
    db.add(AuditLog(
        entity_type="User",
        entity_id=str(user.user_id),
        action="SIGNUP",
        details=f"New {payload.role.lower()} registered: {user.email}"
    ))

    db.commit()
    db.refresh(user)

    token = create_access_token({"sub": str(user.user_id), "email": user.email})

    return AuthResponse(
        user_id=user.user_id,
        email=user.email,
        roles=[r.role_name for r in user.roles],
        access_token=token,
    )


@router.post("/login", response_model=AuthResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """
    Authenticate a user.
    - Verifies the bcrypt hash.
    - Returns user_id, roles, and a JWT access token.
    """
    user = db.query(User).filter(User.email == payload.email).first()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password."
        )

    token = create_access_token({"sub": str(user.user_id), "email": user.email})

    return AuthResponse(
        user_id=user.user_id,
        email=user.email,
        roles=[r.role_name for r in user.roles],
        access_token=token,
    )

@router.post("/logout")
def logout(current_user: User = Depends(get_current_user)):
    """
    Log out a user.
    - Invalidates all cached data specific to this user in Redis.
    """
    from backend.cache import delete_cache_pattern
    
    # Flush all cached entries tied to this user's session
    pattern = f"session:{current_user.user_id}:*"
    delete_cache_pattern(pattern)
    
    return {"success": True, "message": "Successfully logged out and cache cleared."}
