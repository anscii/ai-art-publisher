from app.models import User


def test_create_user_defaults(db):
    u = User(email="friend@example.com", google_sub="g-123")
    db.add(u)
    db.commit()
    db.refresh(u)
    assert u.id
    assert u.email == "friend@example.com"
    assert u.google_sub == "g-123"
    assert u.is_admin is False
    assert u.banned_at is None
    assert u.ban_reason is None
    assert u.created_at is not None


def test_email_unique(db):
    db.add(User(email="dup@example.com", google_sub="g-1"))
    db.commit()
    db.add(User(email="dup@example.com", google_sub="g-2"))
    import pytest
    from sqlalchemy.exc import IntegrityError

    with pytest.raises(IntegrityError):
        db.commit()
