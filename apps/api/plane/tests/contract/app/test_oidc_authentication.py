# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid
from unittest.mock import patch

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from plane.authentication.adapter.error import (
    AUTHENTICATION_ERROR_CODES,
    AuthenticationException,
)
from plane.authentication.utils.user_auth_workflow import post_user_auth_workflow
from plane.db.models import User
from plane.license.models import Instance


@pytest.fixture
def configured_instance(db):
    instance_id = uuid.uuid4() if not Instance.objects.exists() else Instance.objects.first().id
    instance, _ = Instance.objects.update_or_create(
        id=instance_id,
        defaults={
            "instance_name": "OIDC Test Instance",
            "instance_id": str(uuid.uuid4()),
            "current_version": "1.0.0",
            "domain": "http://localhost:8000",
            "last_checked_at": timezone.now(),
            "is_setup_done": True,
        },
    )
    return instance


@pytest.fixture
def django_client():
    return Client(HTTP_USER_AGENT="Mozilla/5.0 (X11; Ubuntu; Linux x86_64)")


@pytest.fixture
def auth_user(db):
    user = User.objects.create(email="oidc-user@plane.so", username="oidc-user")
    user.set_password("user@123")
    user.save()
    return user


@pytest.mark.contract
@pytest.mark.django_db
@patch("plane.authentication.views.app.oidc.OIDCOAuthProvider")
def test_oidc_app_initiate_redirects_to_provider_and_stores_session(
    mock_provider_class,
    django_client,
    configured_instance,
):
    mock_provider_class.return_value.get_auth_url.return_value = "https://auth.example.com/oidc/auth"

    response = django_client.get(reverse("oidc-initiate"), {"next_path": "/kallistomed"}, follow=False)

    assert response.status_code == 302
    assert response.url == "https://auth.example.com/oidc/auth"

    session = django_client.session
    assert session.get("state")
    assert session.get("oidc_nonce")
    assert session.get("next_path") == "/kallistomed"
    assert mock_provider_class.call_args.kwargs["state"] == session["state"]
    assert mock_provider_class.call_args.kwargs["nonce"] == session["oidc_nonce"]


@pytest.mark.contract
@pytest.mark.django_db
@patch("plane.authentication.views.app.oidc.get_safe_redirect_url", return_value="https://plane.example.com/kallistomed")
@patch("plane.authentication.views.app.oidc.user_login")
@patch("plane.authentication.views.app.oidc.OIDCOAuthProvider")
def test_oidc_app_callback_authenticates_and_redirects(
    mock_provider_class,
    mock_user_login,
    mock_safe_redirect,
    django_client,
    configured_instance,
    auth_user,
):
    session = django_client.session
    session["state"] = "oidc-state"
    session["oidc_nonce"] = "oidc-nonce"
    session["next_path"] = "/kallistomed"
    session.save()

    mock_provider_class.return_value.authenticate.return_value = auth_user

    response = django_client.get(
        reverse("oidc-callback"),
        {"code": "oidc-code", "state": "oidc-state"},
        follow=False,
    )

    assert response.status_code == 302
    assert response.url == "https://plane.example.com/kallistomed"
    mock_user_login.assert_called_once()
    mock_safe_redirect.assert_called_once()
    assert mock_provider_class.call_args.kwargs["callback"] is post_user_auth_workflow
    assert mock_provider_class.call_args.kwargs["expected_nonce"] == "oidc-nonce"
    session = django_client.session
    assert session.get("state") is None
    assert session.get("oidc_nonce") is None


@pytest.mark.contract
@pytest.mark.django_db
@patch("plane.authentication.views.app.oidc.get_safe_redirect_url", return_value="https://plane.example.com/login?error=1")
@patch("plane.authentication.views.app.oidc.OIDCOAuthProvider")
def test_oidc_app_callback_rejects_state_mismatch_and_clears_session(
    mock_provider_class,
    mock_safe_redirect,
    django_client,
    configured_instance,
):
    session = django_client.session
    session["state"] = "expected-state"
    session["oidc_nonce"] = "oidc-nonce"
    session["next_path"] = "/kallistomed"
    session.save()

    response = django_client.get(
        reverse("oidc-callback"),
        {"code": "oidc-code", "state": "wrong-state"},
        follow=False,
    )

    assert response.status_code == 302
    assert response.url == "https://plane.example.com/login?error=1"
    mock_provider_class.assert_not_called()
    mock_safe_redirect.assert_called_once()
    session = django_client.session
    assert session.get("state") is None
    assert session.get("oidc_nonce") is None


@pytest.mark.contract
@pytest.mark.django_db
@patch("plane.authentication.views.space.oidc.base_host", return_value="https://plane.example.com/spaces/")
@patch("plane.authentication.views.space.oidc.OIDCOAuthProvider")
def test_oidc_space_initiate_uses_space_callback_path(
    mock_provider_class,
    mock_base_host,
    django_client,
    configured_instance,
):
    mock_provider_class.return_value.get_auth_url.return_value = "https://auth.example.com/oidc/auth"

    response = django_client.get(reverse("space-oidc-initiate"), {"next_path": "/issues"}, follow=False)

    assert response.status_code == 302
    assert response.url == "https://auth.example.com/oidc/auth"
    assert mock_provider_class.call_args.kwargs["redirect_path"] == "/auth/spaces/oidc/callback/"
    assert mock_provider_class.call_args.kwargs["state"] == django_client.session["state"]
    assert mock_provider_class.call_args.kwargs["nonce"] == django_client.session["oidc_nonce"]
    mock_base_host.assert_called()
    session = django_client.session
    assert session.get("next_path") == "/issues"


@pytest.mark.contract
@pytest.mark.django_db
@patch("plane.authentication.views.space.oidc.url_has_allowed_host_and_scheme", return_value=True)
@patch("plane.authentication.views.space.oidc.user_login")
@patch("plane.authentication.views.space.oidc.OIDCOAuthProvider")
def test_oidc_space_callback_authenticates_and_redirects_to_space_path(
    mock_provider_class,
    mock_user_login,
    mock_allowed_redirect,
    django_client,
    configured_instance,
    auth_user,
):
    session = django_client.session
    session["state"] = "space-oidc-state"
    session["oidc_nonce"] = "space-oidc-nonce"
    session["host"] = "https://plane.example.com/spaces/"
    session["next_path"] = "/kallistomed"
    session.save()

    mock_provider_class.return_value.authenticate.return_value = auth_user

    response = django_client.get(
        reverse("space-oidc-callback"),
        {"code": "oidc-code", "state": "space-oidc-state"},
        follow=False,
    )

    assert response.status_code == 302
    assert response.url == "https://plane.example.com/spaces/kallistomed"
    mock_user_login.assert_called_once()
    mock_allowed_redirect.assert_called_once()
    assert mock_provider_class.call_args.kwargs["callback"] is post_user_auth_workflow
    assert mock_provider_class.call_args.kwargs["expected_nonce"] == "space-oidc-nonce"
    session = django_client.session
    assert session.get("state") is None
    assert session.get("oidc_nonce") is None


@pytest.mark.contract
@pytest.mark.django_db
@patch("plane.authentication.views.app.oidc.get_safe_redirect_url", return_value="https://plane.example.com/login?error=oidc")
@patch(
    "plane.authentication.views.app.oidc.OIDCOAuthProvider",
    side_effect=AuthenticationException(
        error_code=AUTHENTICATION_ERROR_CODES["OIDC_NOT_CONFIGURED"],
        error_message="OIDC_NOT_CONFIGURED",
    ),
)
def test_oidc_app_initiate_redirects_safely_when_oidc_is_disabled(
    mock_provider_class,
    mock_safe_redirect,
    django_client,
    configured_instance,
):
    response = django_client.get(reverse("oidc-initiate"), {"next_path": "/kallistomed"}, follow=False)

    assert response.status_code == 302
    assert response.url == "https://plane.example.com/login?error=oidc"
    mock_provider_class.assert_called_once()
    mock_safe_redirect.assert_called_once()


@pytest.mark.contract
@pytest.mark.django_db
@patch("plane.authentication.views.app.oidc.get_safe_redirect_url", return_value="https://plane.example.com/login?error=oidc")
@patch(
    "plane.authentication.views.app.oidc.OIDCOAuthProvider",
    side_effect=AuthenticationException(
        error_code=AUTHENTICATION_ERROR_CODES["OIDC_NOT_CONFIGURED"],
        error_message="OIDC_NOT_CONFIGURED",
    ),
)
def test_oidc_app_callback_rejects_direct_hit_when_oidc_is_disabled(
    mock_provider_class,
    mock_safe_redirect,
    django_client,
    configured_instance,
):
    session = django_client.session
    session["state"] = "oidc-state"
    session["oidc_nonce"] = "oidc-nonce"
    session["next_path"] = "/kallistomed"
    session.save()

    response = django_client.get(
        reverse("oidc-callback"),
        {"code": "oidc-code", "state": "oidc-state"},
        follow=False,
    )

    assert response.status_code == 302
    assert response.url == "https://plane.example.com/login?error=oidc"
    mock_provider_class.assert_called_once()
    mock_safe_redirect.assert_called_once()


@pytest.mark.contract
@pytest.mark.django_db
@patch("plane.authentication.views.mobile.oidc.OIDCOAuthProvider")
def test_oidc_mobile_initiate_uses_mobile_callback_path(
    mock_provider_class,
    django_client,
    configured_instance,
):
    mock_provider_class.return_value.get_auth_url.return_value = "https://auth.example.com/oidc/auth"

    response = django_client.get(reverse("mobile-oidc-initiate"), {"next_path": "/kallistomed"}, follow=False)

    assert response.status_code == 302
    assert response.url == "https://auth.example.com/oidc/auth"
    assert mock_provider_class.call_args.kwargs["redirect_path"] == "/auth/mobile/oidc/callback/"
    assert mock_provider_class.call_args.kwargs["state"] == django_client.session["state"]
    assert mock_provider_class.call_args.kwargs["nonce"] == django_client.session["oidc_nonce"]
    session = django_client.session
    assert session.get("next_path") == "/kallistomed"


@pytest.mark.contract
@pytest.mark.django_db
@patch("plane.authentication.views.mobile.oidc.get_safe_redirect_url", return_value="https://plane.example.com/kallistomed")
@patch("plane.authentication.views.mobile.oidc.user_login")
@patch("plane.authentication.views.mobile.oidc.OIDCOAuthProvider")
def test_oidc_mobile_callback_authenticates_and_redirects(
    mock_provider_class,
    mock_user_login,
    mock_safe_redirect,
    django_client,
    configured_instance,
    auth_user,
):
    session = django_client.session
    session["state"] = "mobile-oidc-state"
    session["oidc_nonce"] = "mobile-oidc-nonce"
    session["next_path"] = "/kallistomed"
    session.save()

    mock_provider_class.return_value.authenticate.return_value = auth_user

    response = django_client.get(
        reverse("mobile-oidc-callback"),
        {"code": "oidc-code", "state": "mobile-oidc-state"},
        follow=False,
    )

    assert response.status_code == 302
    assert response.url == "https://plane.example.com/kallistomed"
    mock_user_login.assert_called_once()
    mock_safe_redirect.assert_called_once()
    assert mock_provider_class.call_args.kwargs["callback"] is post_user_auth_workflow
    assert mock_provider_class.call_args.kwargs["redirect_path"] == "/auth/mobile/oidc/callback/"
    assert mock_provider_class.call_args.kwargs["expected_nonce"] == "mobile-oidc-nonce"
    session = django_client.session
    assert session.get("state") is None
    assert session.get("oidc_nonce") is None


@pytest.mark.contract
@pytest.mark.django_db
@patch("plane.authentication.views.app.oidc.get_safe_redirect_url", return_value="https://plane.example.com/login?error=oidc")
@patch("plane.authentication.views.app.oidc.log_exception")
@patch("plane.authentication.views.app.oidc.OIDCOAuthProvider")
def test_oidc_app_callback_redirects_safely_on_unexpected_provider_error(
    mock_provider_class,
    mock_log_exception,
    mock_safe_redirect,
    django_client,
    configured_instance,
):
    session = django_client.session
    session["state"] = "oidc-state"
    session["oidc_nonce"] = "oidc-nonce"
    session["next_path"] = "/kallistomed"
    session.save()

    mock_provider_class.return_value.authenticate.side_effect = RuntimeError("boom")

    response = django_client.get(
        reverse("oidc-callback"),
        {"code": "oidc-code", "state": "oidc-state"},
        follow=False,
    )

    assert response.status_code == 302
    assert response.url == "https://plane.example.com/login?error=oidc"
    mock_log_exception.assert_called_once()
    mock_safe_redirect.assert_called_once()


@pytest.mark.contract
@pytest.mark.django_db
@patch("plane.authentication.views.space.oidc.get_safe_redirect_url", return_value="https://plane.example.com/spaces/login?error=oidc")
@patch("plane.authentication.views.space.oidc.log_exception")
@patch("plane.authentication.views.space.oidc.OIDCOAuthProvider")
def test_oidc_space_callback_redirects_safely_on_unexpected_provider_error(
    mock_provider_class,
    mock_log_exception,
    mock_safe_redirect,
    django_client,
    configured_instance,
):
    session = django_client.session
    session["state"] = "space-oidc-state"
    session["oidc_nonce"] = "space-oidc-nonce"
    session["host"] = "https://plane.example.com/spaces/"
    session["next_path"] = "/kallistomed"
    session.save()

    mock_provider_class.return_value.authenticate.side_effect = RuntimeError("boom")

    response = django_client.get(
        reverse("space-oidc-callback"),
        {"code": "oidc-code", "state": "space-oidc-state"},
        follow=False,
    )

    assert response.status_code == 302
    assert response.url == "https://plane.example.com/spaces/login?error=oidc"
    mock_log_exception.assert_called_once()
    mock_safe_redirect.assert_called_once()
