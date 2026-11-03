from __future__ import annotations

import pytest

from muse_auth import resolve_mailbox_service, validate_tuan89_mailbox_url


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


def test_resolve_mailbox_service_supports_tuan89():
    svc = resolve_mailbox_service(
        "user@tuan89.site",
        "https://tuan89.site/mail/?email=user%40tuan89.site",
    )
    assert svc["provider"] == "tuan89"
    assert svc["origin"] == "https://tuan89.site"
    assert svc["api_url"] == "https://tuan89.site/api/temp-mail/inbox"
    assert svc["email"] == "user@tuan89.site"


def test_resolve_mailbox_service_supports_mrhulkstore():
    svc = resolve_mailbox_service(
        "user@domain.com",
        "https://api.mrhulkstore.store/otp?mail=user%40domain.com&sig=7abcdef",
    )
    assert svc["provider"] == "mrhulkstore"
    assert svc["origin"] == "https://api.mrhulkstore.store"
    assert svc["api_url"] == "https://api.mrhulkstore.store/api/v1/otp/fetch"
    assert svc["sig"] == "7abcdef"
    assert svc["email"] == "user@domain.com"


def test_resolve_mailbox_service_normalizes_mrhulkstore_hostname_and_pipe_path():
    svc = resolve_mailbox_service(
        "user@domain.com",
        "mrhulkstore.store|otp?mail=user%40domain.com&sig=7abcdef",
    )
    assert svc["provider"] == "mrhulkstore"
    assert svc["origin"] == "https://api.mrhulkstore.store"
    assert svc["api_url"] == "https://api.mrhulkstore.store/api/v1/otp/fetch"
    assert svc["sig"] == "7abcdef"


def test_resolve_mailbox_service_rejects_email_mismatch():
    with pytest.raises(ValueError):
        resolve_mailbox_service(
            "user@domain.com",
            "https://api.mrhulkstore.store/otp?mail=other%40domain.com&sig=7abcdef",
        )
