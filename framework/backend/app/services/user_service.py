"""User business operations."""

from sqlalchemy.orm import Session

from app.core.security import get_password_hash, verify_password
from app.models.user import User
from app.schemas.user import UserRegister


def get_user_by_id(db: Session, user_id: int) -> User | None:
    """Return a user by primary key."""

    return db.get(User, user_id)


def get_user_by_username(db: Session, username: str) -> User | None:
    """Return a user by username."""

    return db.query(User).filter(User.username == username).first()


def create_user(db: Session, user_in: UserRegister) -> User:
    """Create a new user with a hashed password."""

    db_user = User(
        username=user_in.username,
        password_hash=get_password_hash(user_in.password),
        real_name=user_in.real_name,
        role=user_in.role,
        student_id=user_in.student_id,
        class_name=user_in.class_name,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return db_user


def authenticate_user(db: Session, username: str, password: str) -> User | None:
    """Authenticate username and password, returning the user on success."""

    user = get_user_by_username(db, username)
    if user is None:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
