from __future__ import annotations

import pytest

from muse_auth import validate_tuan89_mailbox_url


def test_validate_tuan89_mailbox_url_accepts_matching_email():
    origin = validate_tuan89_mailbox_url(
        "user@tuan89.site",
        "https://tuan89.site/mail/?email=user%40tuan89.site",
    )
    assert origin == "https://tuan89.site"


@pytest.mark.parametrize(
    "url",
    [
        "http://tuan89.site/mail/?email=user%40tuan89.site",
        "https://example.com/mail/?email=user%40tuan89.site",
        "https://tuan89.site/mail/?email=other%40tuan89.site",
    ],
)
def test_validate_tuan89_mailbox_url_rejects_unsafe_or_mismatched_url(url):
    with pytest.raises(ValueError):
        validate_tuan89_mailbox_url("user@tuan89.site", url)
