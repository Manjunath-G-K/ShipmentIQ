"""Database-backed authentication and demo-user provisioning services."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.core.config import Settings, get_settings
from app.core.security import hash_password, validate_password, verify_password
from app.db.models import Role, RoleName, User


@dataclass(frozen=True)
class DemoUserSpec:
    email: str
    password: str
    role_name: RoleName


def normalize_email(email: str) -> str:
    return email.strip().casefold()


def authenticate_user(session: Session, email: str, password: str) -> User | None:
    """Return an active user only when the supplied password verifies."""

    user = session.scalar(
        select(User)
        .options(selectinload(User.roles))
        .where(User.email == normalize_email(email))
    )
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def get_user_with_roles(session: Session, user_id) -> User | None:
    return session.scalar(
        select(User).options(selectinload(User.roles)).where(User.id == user_id)
    )


def user_roles(user: User) -> list[str]:
    return sorted(role.name for role in user.roles)


def demo_user_specs(settings: Settings | None = None) -> list[DemoUserSpec]:
    settings = settings or get_settings()
    values = [
        (
            settings.demo_executive_email,
            settings.demo_executive_password,
            RoleName.DOCUMENTATION_EXECUTIVE,
        ),
        (
            settings.demo_manager_email,
            settings.demo_manager_password,
            RoleName.DOCUMENTATION_MANAGER,
        ),
    ]
    specs: list[DemoUserSpec] = []
    for email, password, role_name in values:
        if not email or not password:
            raise ValueError(
                "All demo user email and password environment variables are required"
            )
        validate_password(password)
        specs.append(
            DemoUserSpec(
                email=normalize_email(email), password=password, role_name=role_name
            )
        )
    return specs


def seed_demo_users(session: Session, settings: Settings | None = None) -> list[User]:
    """Create or reconcile demo users without committing the caller's transaction."""

    settings = settings or get_settings()
    if not settings.seed_demo_users:
        raise ValueError("SEED_DEMO_USERS must be true to seed demo users")
    if settings.environment.lower() == "production":
        raise ValueError("Demo user seeding is disabled in production")

    roles = {
        role.name: role
        for role in session.scalars(
            select(Role).where(
                Role.name.in_([role_name.value for role_name in RoleName])
            )
        )
    }
    for role_name in RoleName:
        roles.setdefault(role_name.value, Role(name=role_name.value))
    for role in roles.values():
        if role not in session:
            session.add(role)
    session.flush()

    users: list[User] = []
    for spec in demo_user_specs(settings):
        user = session.scalar(
            select(User).options(selectinload(User.roles)).where(User.email == spec.email)
        )
        if user is None:
            user = User(
                email=spec.email,
                password_hash=hash_password(spec.password),
                is_active=True,
            )
            session.add(user)
            session.flush()
        role = roles[spec.role_name.value]
        if role not in user.roles:
            user.roles.append(role)
        users.append(user)

    session.flush()
    return users
