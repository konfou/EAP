import pytest

from apps.api import auth


def test_get_role_accepts_valid_role():
    assert auth.get_role("operator") == "operator"


def test_get_role_rejects_invalid_role():
    with pytest.raises(Exception):
        auth.get_role("unknown")


def test_require_role_allows_higher_role():
    checker = auth.require_role("operator")
    assert checker("admin") == "admin"


def test_require_role_blocks_lower_role():
    checker = auth.require_role("admin")
    with pytest.raises(Exception):
        checker("reader")
