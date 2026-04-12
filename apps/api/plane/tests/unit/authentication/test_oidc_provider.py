# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock, patch

import pytest
from django.core.cache import cache
from django.test import RequestFactory

from plane.authentication.adapter.error import AuthenticationException
from plane.authentication.provider.oauth.oidc import OIDCOAuthProvider


def _mock_response(payload):
    response = Mock()
    response.json.return_value = payload
    response.raise_for_status.return_value = None
    return response


@pytest.fixture
def oidc_request():
    factory = RequestFactory()
    return factory.get("/auth/oidc/", secure=True, HTTP_HOST="plane.example.com")


@pytest.fixture
def oidc_configuration():
    return (
        "https://auth.example.com/realms/kallistomed",
        "plane",
        "top-secret",
        "openid profile email",
        "email",
        "given_name",
        "family_name",
        "sub",
        "groups",
        "Keycloak",
        "1",
        "1",
        "/access/plane",
        "",
        "",
        "",
        "",
    )


@pytest.mark.unit
@patch("plane.authentication.provider.oauth.oidc.requests.get")
@patch("plane.authentication.provider.oauth.oidc.get_configuration_value")
def test_oidc_provider_builds_authorization_url(mock_get_configuration_value, mock_get, oidc_request, oidc_configuration):
    cache.clear()
    mock_get_configuration_value.return_value = oidc_configuration
    mock_get.return_value = _mock_response(
        {
            "authorization_endpoint": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/auth",
            "token_endpoint": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/token",
            "userinfo_endpoint": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/userinfo",
            "jwks_uri": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/certs",
        }
    )

    provider = OIDCOAuthProvider(request=oidc_request, state="state-123")

    parsed_url = urlparse(provider.get_auth_url())
    params = parse_qs(parsed_url.query)

    assert parsed_url.path.endswith("/protocol/openid-connect/auth")
    assert params["client_id"] == ["plane"]
    assert params["state"] == ["state-123"]
    assert params["scope"] == ["openid profile email"]
    assert params["redirect_uri"] == ["https://plane.example.com/auth/oidc/callback/"]


@pytest.mark.unit
def test_oidc_provider_exchanges_token_and_parses_userinfo(oidc_request, oidc_configuration):
    with patch(
        "plane.authentication.provider.oauth.oidc.get_configuration_value",
        return_value=oidc_configuration,
    ), patch.object(
        OIDCOAuthProvider,
        "get_discovery_document",
        return_value={
            "authorization_endpoint": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/auth",
            "token_endpoint": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/token",
            "userinfo_endpoint": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/userinfo",
            "jwks_uri": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/certs",
        },
    ), patch.object(
        OIDCOAuthProvider,
        "get_user_token",
        return_value={
            "access_token": "access-token",
            "refresh_token": "refresh-token",
            "expires_in": 300,
            "refresh_expires_in": 1800,
            "id_token": "valid-id-token",
        },
    ), patch.object(
        OIDCOAuthProvider,
        "get_user_response",
        return_value={
            "sub": "kc-user-1",
            "email": "oidc-user@plane.so",
            "email_verified": True,
            "given_name": "OIDC",
            "family_name": "User",
            "preferred_username": "oidc-user",
            "picture": "https://img.example.com/avatar.png",
            "groups": ["/access/plane", "/plane/member"],
        },
    ), patch.object(
        OIDCOAuthProvider,
        "_validate_id_token",
    ):
        provider = OIDCOAuthProvider(request=oidc_request, code="oidc-code")
        provider.set_token_data()
        provider.set_user_data()

    assert provider.token_data["access_token"] == "access-token"
    assert provider.token_data["refresh_token"] == "refresh-token"
    assert provider.token_data["id_token"] == ""
    assert provider.token_data["access_token_expired_at"] is not None
    assert provider.token_data["refresh_token_expired_at"] is not None

    assert provider.user_data["email"] == "oidc-user@plane.so"
    assert provider.user_data["email_verified"] is True
    assert provider.user_data["groups"] == ["/access/plane", "/plane/member"]
    assert provider.user_data["provider_name"] == "Keycloak"
    assert provider.user_data["user"]["provider_id"] == "kc-user-1"
    assert provider.user_data["user"]["display_name"] == "oidc-user"
    assert provider.user_data["user"]["first_name"] == "OIDC"
    assert provider.user_data["user"]["last_name"] == "User"


@pytest.mark.unit
@patch("plane.authentication.provider.oauth.oidc.get_configuration_value")
def test_oidc_provider_requires_basic_configuration(mock_get_configuration_value, oidc_request):
    mock_get_configuration_value.return_value = (
        "",
        "plane",
        "top-secret",
        "openid profile email",
        "email",
        "given_name",
        "family_name",
        "sub",
        "groups",
        "Keycloak",
        "1",
        "1",
        "",
        "",
        "",
        "",
        "",
    )

    with pytest.raises(AuthenticationException) as exc_info:
        OIDCOAuthProvider(request=oidc_request, state="state-123")

    assert exc_info.value.error_message == "OIDC_NOT_CONFIGURED"


@pytest.mark.unit
@patch("plane.authentication.provider.oauth.oidc.get_configuration_value")
def test_oidc_provider_requires_enabled_flag(mock_get_configuration_value, oidc_request):
    mock_get_configuration_value.return_value = (
        "https://auth.example.com/realms/kallistomed",
        "plane",
        "top-secret",
        "openid profile email",
        "email",
        "given_name",
        "family_name",
        "sub",
        "groups",
        "Keycloak",
        "0",
        "1",
        "",
        "",
        "",
        "",
        "",
    )

    with pytest.raises(AuthenticationException) as exc_info:
        OIDCOAuthProvider(request=oidc_request, state="state-123")

    assert exc_info.value.error_message == "OIDC_NOT_CONFIGURED"


@pytest.mark.unit
@patch("plane.authentication.provider.oauth.oidc.get_configuration_value")
def test_oidc_provider_requires_access_group_configuration(mock_get_configuration_value, oidc_request):
    mock_get_configuration_value.return_value = (
        "https://auth.example.com/realms/kallistomed",
        "plane",
        "top-secret",
        "openid profile email",
        "email",
        "given_name",
        "family_name",
        "sub",
        "groups",
        "Keycloak",
        "1",
        "1",
        "",
        "",
        "",
        "",
        "",
    )

    with pytest.raises(AuthenticationException) as exc_info:
        OIDCOAuthProvider(request=oidc_request, state="state-123")

    assert exc_info.value.error_message == "OIDC_NOT_CONFIGURED"


@pytest.mark.unit
def test_oidc_provider_validates_id_token_with_jwks_and_nonce(oidc_request, oidc_configuration):
    with patch(
        "plane.authentication.provider.oauth.oidc.get_configuration_value",
        return_value=oidc_configuration,
    ), patch.object(
        OIDCOAuthProvider,
        "get_discovery_document",
        return_value={
            "authorization_endpoint": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/auth",
            "token_endpoint": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/token",
            "userinfo_endpoint": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/userinfo",
            "jwks_uri": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/certs",
        },
    ), patch("plane.authentication.provider.oauth.oidc.PyJWKClient") as mock_jwk_client_class, patch(
        "plane.authentication.provider.oauth.oidc.jwt.decode",
        return_value={
            "iss": "https://auth.example.com/realms/kallistomed",
            "aud": "plane",
            "exp": 9999999999,
            "iat": 1111111111,
            "nonce": "expected-nonce",
            "sub": "kc-user-1",
        },
    ) as mock_jwt_decode:
        signing_key = Mock()
        signing_key.key = "signing-key"
        signing_key.algorithm_name = "RS256"
        mock_jwk_client_class.return_value.get_signing_key_from_jwt.return_value = signing_key

        provider = OIDCOAuthProvider(request=oidc_request, code="oidc-code", expected_nonce="expected-nonce")
        provider._validate_id_token({"id_token": "signed-token"})

    mock_jwk_client_class.assert_called_once_with(
        "https://auth.example.com/realms/kallistomed/protocol/openid-connect/certs",
        cache_keys=True,
        cache_jwk_set=True,
        lifespan=provider.discovery_cache_ttl,
        timeout=provider.request_timeout,
    )
    mock_jwt_decode.assert_called_once_with(
        "signed-token",
        "signing-key",
        algorithms=["RS256"],
        audience="plane",
        issuer="https://auth.example.com/realms/kallistomed",
        options={"require": ["exp", "iat", "iss", "aud"]},
    )
    assert provider.id_token_claims["sub"] == "kc-user-1"


@pytest.mark.unit
def test_oidc_provider_rejects_userinfo_without_sub(oidc_request, oidc_configuration):
    with patch(
        "plane.authentication.provider.oauth.oidc.get_configuration_value",
        return_value=oidc_configuration,
    ), patch.object(
        OIDCOAuthProvider,
        "get_discovery_document",
        return_value={
            "authorization_endpoint": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/auth",
            "token_endpoint": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/token",
            "userinfo_endpoint": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/userinfo",
            "jwks_uri": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/certs",
        },
    ), patch.object(
        OIDCOAuthProvider,
        "get_user_response",
        return_value={"email": "oidc-user@plane.so", "email_verified": True},
    ):
        provider = OIDCOAuthProvider(request=oidc_request, code="oidc-code")
        with pytest.raises(AuthenticationException) as exc_info:
            provider.set_user_data()

    assert exc_info.value.error_message == "OIDC_OAUTH_PROVIDER_ERROR"


@pytest.mark.unit
def test_oidc_provider_redacts_access_token_when_userinfo_json_is_invalid(oidc_request, oidc_configuration):
    with patch(
        "plane.authentication.provider.oauth.oidc.get_configuration_value",
        return_value=oidc_configuration,
    ), patch.object(
        OIDCOAuthProvider,
        "get_discovery_document",
        return_value={
            "authorization_endpoint": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/auth",
            "token_endpoint": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/token",
            "userinfo_endpoint": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/userinfo",
            "jwks_uri": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/certs",
        },
    ), patch(
        "plane.authentication.adapter.oauth.requests.get"
    ) as mock_requests_get:
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = ValueError("invalid-json")
        mock_requests_get.return_value = mock_response

        provider = OIDCOAuthProvider(request=oidc_request, code="oidc-code")
        provider.token_data = {"access_token": "super-secret-token"}

        with patch.object(provider.logger, "warning") as mock_warning, pytest.raises(AuthenticationException) as exc_info:
            provider.get_user_response()

    assert exc_info.value.error_message == "OIDC_OAUTH_PROVIDER_ERROR"
    assert mock_warning.call_args.kwargs["extra"] == {
        "userinfo_url": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/userinfo",
        "provider": "oidc",
    }
    assert "super-secret-token" not in repr(mock_warning.call_args)
    assert mock_requests_get.call_args.kwargs["timeout"] == provider.request_timeout


@pytest.mark.unit
def test_oidc_provider_maps_invalid_token_json_to_auth_error(oidc_request, oidc_configuration):
    with patch(
        "plane.authentication.provider.oauth.oidc.get_configuration_value",
        return_value=oidc_configuration,
    ), patch.object(
        OIDCOAuthProvider,
        "get_discovery_document",
        return_value={
            "authorization_endpoint": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/auth",
            "token_endpoint": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/token",
            "userinfo_endpoint": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/userinfo",
            "jwks_uri": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/certs",
        },
    ), patch(
        "plane.authentication.adapter.oauth.requests.post"
    ) as mock_requests_post:
        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.side_effect = ValueError("invalid-json")
        mock_requests_post.return_value = mock_response

        provider = OIDCOAuthProvider(request=oidc_request, code="oidc-code")

        with pytest.raises(AuthenticationException) as exc_info:
            provider.get_user_token(data={"grant_type": "authorization_code"})

    assert exc_info.value.error_message == "OIDC_OAUTH_PROVIDER_ERROR"
    assert mock_requests_post.call_args.kwargs["timeout"] == provider.request_timeout


@pytest.mark.unit
@patch("plane.authentication.provider.oauth.oidc.requests.get")
@patch("plane.authentication.provider.oauth.oidc.get_configuration_value")
def test_oidc_provider_maps_invalid_discovery_json_to_not_configured(
    mock_get_configuration_value, mock_requests_get, oidc_request, oidc_configuration
):
    cache.clear()
    mock_get_configuration_value.return_value = oidc_configuration
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.side_effect = ValueError("invalid-json")
    mock_requests_get.return_value = mock_response

    with pytest.raises(AuthenticationException) as exc_info:
        OIDCOAuthProvider(request=oidc_request, state="state-123")

    assert exc_info.value.error_message == "OIDC_NOT_CONFIGURED"


@pytest.mark.unit
def test_oidc_provider_rejects_id_token_with_mismatched_nonce(oidc_request, oidc_configuration):
    with patch(
        "plane.authentication.provider.oauth.oidc.get_configuration_value",
        return_value=oidc_configuration,
    ), patch.object(
        OIDCOAuthProvider,
        "get_discovery_document",
        return_value={
            "authorization_endpoint": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/auth",
            "token_endpoint": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/token",
            "userinfo_endpoint": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/userinfo",
            "jwks_uri": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/certs",
        },
    ), patch("plane.authentication.provider.oauth.oidc.PyJWKClient") as mock_jwk_client_class, patch(
        "plane.authentication.provider.oauth.oidc.jwt.decode",
        return_value={
            "iss": "https://auth.example.com/realms/kallistomed",
            "aud": "plane",
            "exp": 9999999999,
            "iat": 1111111111,
            "nonce": "wrong-nonce",
            "sub": "kc-user-1",
        },
    ):
        signing_key = Mock()
        signing_key.key = "signing-key"
        signing_key.algorithm_name = "RS256"
        mock_jwk_client_class.return_value.get_signing_key_from_jwt.return_value = signing_key

        provider = OIDCOAuthProvider(request=oidc_request, code="oidc-code", expected_nonce="expected-nonce")
        with pytest.raises(AuthenticationException) as exc_info:
            provider._validate_id_token({"id_token": "signed-token"})

    assert exc_info.value.error_message == "OIDC_OAUTH_PROVIDER_ERROR"
