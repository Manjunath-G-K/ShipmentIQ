"""Explicit, environment-driven, idempotent demo-user provisioning."""

from app.core.config import get_settings
from app.db.session import get_session_factory
from app.modules.auth.service import seed_demo_users


def main() -> None:
    settings = get_settings()
    with get_session_factory()() as session:
        try:
            users = seed_demo_users(session, settings)
            session.commit()
        except Exception:
            session.rollback()
            raise
    print(f"Verified {len(users)} demo users and their required roles.")


if __name__ == "__main__":
    main()
