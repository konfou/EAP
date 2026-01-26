from apps.api.db import get_db


def test_get_db_yields_session():
    generator = get_db()
    session = next(generator)
    try:
        assert session is not None
        assert session.is_active
    finally:
        generator.close()
