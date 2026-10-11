"""Right to a paid report never depends on who typed which email.

The rule the guest funnel was built on: **email is a communication
attribute, never entitlement identity**. Access comes from a verified
provider event → purchase → unlock, and from nothing else.

Today this holds structurally — there is no email on the purchase model
and none in the webhook path. That is exactly why it needs a test:
an invariant that is true by accident stops being true the first time
somebody adds a convenient field.

No database and no network: this reads the code.
"""

from __future__ import annotations

import ast
import inspect
from pathlib import Path

APP = Path(__file__).resolve().parents[1] / "app"


def _entitlement_sources() -> dict[str, str]:
    """The modules that decide whether a paid report may be shown."""
    return {
        "application/guest.py": (APP / "application" / "guest.py").read_text(encoding="utf-8"),
        "application/purchases.py": (
            APP / "application" / "purchases.py"
        ).read_text(encoding="utf-8"),
        "models/purchase.py": (APP / "models" / "purchase.py").read_text(encoding="utf-8"),
        "models/guest.py": (APP / "models" / "guest.py").read_text(encoding="utf-8"),
    }


def test_purchase_and_unlock_records_carry_no_email():
    """Storing it would be the first step to matching on it."""
    for name in ("models/purchase.py", "models/guest.py"):
        source = _entitlement_sources()[name]
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
                assert "email" not in node.target.id.lower(), (
                    f"{name}: entitlement record grew an email column ({node.target.id})"
                )


def test_the_functions_that_grant_access_never_read_an_email():
    """`is_unlocked` and `paid_content_denied` are the whole authority."""
    from app.application import guest as guest_app

    for func in (guest_app.is_unlocked, guest_app.paid_content_denied,
                 guest_app.has_unlock_history):
        body = inspect.getsource(func).lower()
        assert "email" not in body, f"{func.__name__} consults an email"


def test_unlocking_is_driven_by_a_verified_purchase_not_by_a_person():
    """The unlock row points at a purchase — the payment fact, not a user.

    A RESTRICT foreign key to the purchase is what makes the entitlement
    traceable to money that actually arrived.
    """
    from app.models.guest import AuditUnlock

    columns = {c.name for c in AuditUnlock.__table__.columns}
    assert "purchase_id" in columns
    assert not {c for c in columns if "email" in c or "user" in c}, (
        f"unlock is tied to a person, not to a payment: {columns}"
    )
