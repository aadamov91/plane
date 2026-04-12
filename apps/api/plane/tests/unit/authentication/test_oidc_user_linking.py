# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import uuid
from unittest.mock import Mock, patch

import pytest
from django.db import IntegrityError
from django.test import RequestFactory

from plane.authentication.provider.oauth.oidc import OIDCOAuthProvider
from plane.authentication.adapter.error import AuthenticationException
from plane.db.models import Account, Profile, User, WorkspaceMember
from plane.tests.factories import WorkspaceFactory


@pytest.fixture
def oidc_request():
    factory = RequestFactory()
    return factory.get(
        "/auth/oidc/",
        secure=True,
        HTTP_HOST="plane.example.com",
        HTTP_USER_AGENT="Mozilla/5.0 (X11; Ubuntu; Linux x86_64)",
    )


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


def build_provider(request, configuration):
    with patch(
        "plane.authentication.provider.oauth.oidc.get_configuration_value",
        return_value=configuration,
    ), patch.object(
        OIDCOAuthProvider,
        "get_discovery_document",
        return_value={
            "authorization_endpoint": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/auth",
            "token_endpoint": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/token",
            "userinfo_endpoint": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/userinfo",
            "jwks_uri": "https://auth.example.com/realms/kallistomed/protocol/openid-connect/certs",
        },
    ):
        return OIDCOAuthProvider(request=request, code="oidc-code")


def apply_user_payload(provider, email, provider_id, groups=None):
    provider.user_data = {
        "email": email,
        "email_verified": True,
        "groups": groups or ["/access/plane", "/plane/member"],
        "provider_name": "Keycloak",
        "user": {
            "provider_id": provider_id,
            "display_name": "oidc-user",
            "first_name": "OIDC",
            "last_name": "User",
            "is_password_autoset": True,
        },
    }
    provider.token_data = {
        "access_token": "new-access-token",
        "refresh_token": "refresh-token",
        "access_token_expired_at": None,
        "refresh_token_expired_at": None,
        "id_token": "id-token",
    }


def oidc_configuration_with_access_and_workspace(
    access_group="/access/plane",
    admin_group="",
    member_group="",
    guest_group="",
    workspace_slug="kallistomed",
):
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
        access_group,
        admin_group,
        member_group,
        guest_group,
        workspace_slug,
    )


@pytest.mark.unit
@pytest.mark.django_db
def test_oidc_complete_login_or_signup_prefers_existing_account_by_sub(oidc_request, oidc_configuration):
    existing_user = User.objects.create(email="existing@plane.so", username=uuid.uuid4().hex)
    existing_user.set_password("user@123")
    existing_user.save()

    Account.objects.create(
        user=existing_user,
        provider="oidc",
        provider_instance="https://auth.example.com/realms/kallistomed",
        provider_account_id="kc-user-1",
        access_token="old-access-token",
        refresh_token="old-refresh-token",
        id_token="old-id-token",
    )

    provider = build_provider(request=oidc_request, configuration=oidc_configuration)
    apply_user_payload(provider=provider, email="renamed@plane.so", provider_id="kc-user-1")

    user = provider.complete_login_or_signup()
    account = Account.objects.get(
        provider="oidc",
        provider_instance="https://auth.example.com/realms/kallistomed",
        provider_account_id="kc-user-1",
    )

    assert user.id == existing_user.id
    assert account.user_id == existing_user.id
    assert account.access_token == "new-access-token"
    assert (
        Account.objects.filter(
            provider="oidc",
            provider_instance="https://auth.example.com/realms/kallistomed",
            provider_account_id="kc-user-1",
        ).count()
        == 1
    )


@pytest.mark.unit
@pytest.mark.django_db
def test_oidc_complete_login_or_signup_rejects_existing_local_user_without_explicit_link(
    oidc_request, oidc_configuration
):
    existing_user = User.objects.create(email="existing@plane.so", username=uuid.uuid4().hex)
    existing_user.set_password("user@123")
    existing_user.save()

    provider = build_provider(request=oidc_request, configuration=oidc_configuration)
    apply_user_payload(provider=provider, email="existing@plane.so", provider_id="kc-user-2")

    with pytest.raises(AuthenticationException) as exc_info:
        provider.complete_login_or_signup()

    assert exc_info.value.error_message == "OIDC_ACCOUNT_LINK_CONFLICT"
    assert Account.objects.filter(provider="oidc", provider_account_id="kc-user-2").exists() is False


@pytest.mark.unit
@pytest.mark.django_db
def test_oidc_complete_login_or_signup_rejects_unverified_email_for_existing_local_user(
    oidc_request, oidc_configuration
):
    existing_user = User.objects.create(email="existing@plane.so", username=uuid.uuid4().hex)
    existing_user.set_password("user@123")
    existing_user.save()

    provider = build_provider(request=oidc_request, configuration=oidc_configuration)
    apply_user_payload(provider=provider, email="existing@plane.so", provider_id="kc-user-2")
    provider.user_data["email_verified"] = False

    with pytest.raises(AuthenticationException) as exc_info:
        provider.complete_login_or_signup()

    assert exc_info.value.error_message == "OIDC_EMAIL_NOT_VERIFIED"
    assert Account.objects.filter(provider="oidc", provider_account_id="kc-user-2").exists() is False


@pytest.mark.unit
@pytest.mark.django_db
def test_oidc_complete_login_or_signup_creates_new_user_when_needed(oidc_request, oidc_configuration):
    provider = build_provider(request=oidc_request, configuration=oidc_configuration)
    apply_user_payload(provider=provider, email="new-oidc-user@plane.so", provider_id="kc-user-3")

    user = provider.complete_login_or_signup()
    account = Account.objects.get(
        provider="oidc",
        provider_instance="https://auth.example.com/realms/kallistomed",
        provider_account_id="kc-user-3",
    )

    assert user.email == "new-oidc-user@plane.so"
    assert user.is_password_autoset is True
    assert user.is_email_verified is True
    assert Profile.objects.filter(user=user).exists()
    assert account.user_id == user.id


@pytest.mark.unit
@pytest.mark.django_db
def test_oidc_complete_login_or_signup_rejects_unverified_email_for_new_user(oidc_request, oidc_configuration):
    provider = build_provider(request=oidc_request, configuration=oidc_configuration)
    apply_user_payload(provider=provider, email="unverified@plane.so", provider_id="kc-user-unverified")
    provider.user_data["email_verified"] = False

    with pytest.raises(AuthenticationException) as exc_info:
        provider.complete_login_or_signup()

    assert exc_info.value.error_message == "OIDC_EMAIL_NOT_VERIFIED"
    assert User.objects.filter(email="unverified@plane.so").exists() is False


@pytest.mark.unit
@pytest.mark.django_db
def test_oidc_complete_login_or_signup_marks_new_user_as_signup_for_callback(oidc_request, oidc_configuration):
    callback = Mock()
    provider = build_provider(request=oidc_request, configuration=oidc_configuration)
    provider.callback = callback
    apply_user_payload(provider=provider, email="callback-signup@plane.so", provider_id="kc-user-signup")

    user = provider.complete_login_or_signup()

    callback.assert_called_once()
    assert callback.call_args[0][0].id == user.id
    assert callback.call_args[0][1] is True


@pytest.mark.unit
@pytest.mark.django_db
def test_oidc_complete_login_or_signup_marks_existing_user_as_login_for_callback(oidc_request, oidc_configuration):
    existing_user = User.objects.create(email="existing-callback@plane.so", username=uuid.uuid4().hex)
    existing_user.set_password("user@123")
    existing_user.save()
    Account.objects.create(
        user=existing_user,
        provider="oidc",
        provider_instance="https://auth.example.com/realms/kallistomed",
        provider_account_id="kc-user-existing-callback",
        access_token="old-access-token",
        refresh_token="old-refresh-token",
        id_token="old-id-token",
    )

    callback = Mock()
    provider = build_provider(request=oidc_request, configuration=oidc_configuration)
    provider.callback = callback
    apply_user_payload(provider=provider, email="existing-callback@plane.so", provider_id="kc-user-existing-callback")

    user = provider.complete_login_or_signup()

    callback.assert_called_once()
    assert callback.call_args[0][0].id == user.id
    assert callback.call_args[0][1] is False


@pytest.mark.unit
@pytest.mark.django_db
def test_oidc_complete_login_or_signup_rejects_missing_email(oidc_request, oidc_configuration):
    provider = build_provider(request=oidc_request, configuration=oidc_configuration)
    apply_user_payload(provider=provider, email=None, provider_id="kc-user-no-email")

    with pytest.raises(AuthenticationException) as exc_info:
        provider.complete_login_or_signup()

    assert exc_info.value.error_message == "INVALID_EMAIL"


@pytest.mark.unit
@pytest.mark.django_db
def test_oidc_authenticate_rejects_user_without_access_group(oidc_request):
    provider = build_provider(request=oidc_request, configuration=oidc_configuration_with_access_and_workspace())
    apply_user_payload(provider=provider, email="blocked-user@plane.so", provider_id="kc-user-blocked")
    provider.user_data["groups"] = ["/plane/member"]

    with patch.object(provider, "set_token_data"), patch.object(provider, "set_user_data"), pytest.raises(
        AuthenticationException
    ) as exc_info:
        provider.authenticate()

    assert exc_info.value.error_message == "OIDC_USER_NOT_ALLOWED"
    assert User.objects.filter(email="blocked-user@plane.so").exists() is False


@pytest.mark.unit
@pytest.mark.django_db
def test_oidc_authenticate_rejects_deactivated_existing_user(oidc_request, oidc_configuration):
    existing_user = User.objects.create(
        email="deactivated@plane.so",
        username=uuid.uuid4().hex,
        is_active=False,
    )
    existing_user.set_password("user@123")
    existing_user.save(update_fields=["password", "is_active"])

    Account.objects.create(
        user=existing_user,
        provider="oidc",
        provider_instance="https://auth.example.com/realms/kallistomed",
        provider_account_id="kc-user-deactivated",
        access_token="old-access-token",
        refresh_token="old-refresh-token",
        id_token="old-id-token",
    )

    provider = build_provider(request=oidc_request, configuration=oidc_configuration)
    apply_user_payload(provider=provider, email="deactivated@plane.so", provider_id="kc-user-deactivated")

    with patch.object(provider, "set_token_data"), patch.object(provider, "set_user_data"), pytest.raises(
        AuthenticationException
    ) as exc_info:
        provider.authenticate()

    existing_user.refresh_from_db()
    assert exc_info.value.error_message == "USER_ACCOUNT_DEACTIVATED"
    assert existing_user.is_active is False


@pytest.mark.unit
@pytest.mark.django_db
def test_oidc_authenticate_rejects_provider_instance_collision(oidc_request, oidc_configuration):
    existing_user = User.objects.create(email="collision@plane.so", username=uuid.uuid4().hex)
    existing_user.set_password("user@123")
    existing_user.save()

    Account.objects.create(
        user=existing_user,
        provider="oidc",
        provider_instance="https://old-auth.example.com/realms/kallistomed",
        provider_account_id="kc-collision-user",
        access_token="old-access-token",
        refresh_token="old-refresh-token",
        id_token="old-id-token",
    )

    provider = build_provider(request=oidc_request, configuration=oidc_configuration)
    apply_user_payload(provider=provider, email="collision@plane.so", provider_id="kc-collision-user")

    with patch.object(provider, "set_token_data"), patch.object(provider, "set_user_data"), pytest.raises(
        AuthenticationException
    ) as exc_info:
        provider.authenticate()

    assert exc_info.value.error_message == "OIDC_PROVIDER_INSTANCE_CONFLICT"


@pytest.mark.unit
@pytest.mark.django_db
def test_oidc_authenticate_provisions_default_workspace_membership(oidc_request):
    workspace = WorkspaceFactory(slug="kallistomed")
    provider = build_provider(request=oidc_request, configuration=oidc_configuration_with_access_and_workspace())
    apply_user_payload(provider=provider, email="workspace-user@plane.so", provider_id="kc-user-workspace")

    with patch.object(provider, "set_token_data"), patch.object(provider, "set_user_data"):
        user = provider.authenticate()

    workspace_member = WorkspaceMember.objects.get(workspace=workspace, member=user)
    profile = Profile.objects.get(user=user)

    assert workspace_member.role == 15
    assert workspace_member.is_active is True
    assert profile.last_workspace_id == workspace.id
    assert profile.language == "ru"
    assert profile.is_onboarded is True
    assert profile.onboarding_step == {
        "profile_complete": True,
        "workspace_create": True,
        "workspace_invite": True,
        "workspace_join": True,
    }
    assert profile.is_mobile_onboarded is True
    assert profile.mobile_onboarding_step == {
        "profile_complete": True,
        "workspace_create": True,
        "workspace_join": True,
    }


@pytest.mark.unit
@pytest.mark.django_db
def test_oidc_authenticate_skips_onboarding_without_default_workspace(oidc_request, oidc_configuration):
    provider = build_provider(request=oidc_request, configuration=oidc_configuration)
    apply_user_payload(provider=provider, email="mobile-user@plane.so", provider_id="kc-user-mobile")

    with patch.object(provider, "set_token_data"), patch.object(provider, "set_user_data"):
        user = provider.authenticate()

    profile = Profile.objects.get(user=user)

    assert profile.last_workspace_id is None
    assert profile.language == "ru"
    assert profile.is_onboarded is True
    assert profile.onboarding_step == {
        "profile_complete": True,
        "workspace_create": True,
        "workspace_invite": True,
        "workspace_join": True,
    }
    assert profile.is_mobile_onboarded is True
    assert profile.mobile_onboarding_step == {
        "profile_complete": True,
        "workspace_create": True,
        "workspace_join": True,
    }


@pytest.mark.unit
@pytest.mark.django_db
def test_oidc_authenticate_preserves_existing_profile_language(oidc_request, oidc_configuration):
    existing_user = User.objects.create(email="existing-language@plane.so", username=uuid.uuid4().hex)
    existing_user.set_password("user@123")
    existing_user.save()
    profile = Profile.objects.create(
        user=existing_user,
        language="de",
        is_onboarded=False,
        is_mobile_onboarded=False,
    )
    Account.objects.create(
        user=existing_user,
        provider="oidc",
        provider_instance="https://auth.example.com/realms/kallistomed",
        provider_account_id="kc-user-language",
        access_token="old-access-token",
        refresh_token="old-refresh-token",
        id_token="old-id-token",
    )

    provider = build_provider(request=oidc_request, configuration=oidc_configuration)
    apply_user_payload(provider=provider, email="existing-language@plane.so", provider_id="kc-user-language")

    with patch.object(provider, "set_token_data"), patch.object(provider, "set_user_data"):
        user = provider.authenticate()

    profile.refresh_from_db()

    assert user.id == existing_user.id
    assert profile.language == "de"
    assert profile.is_onboarded is True
    assert profile.is_mobile_onboarded is True


@pytest.mark.unit
@pytest.mark.django_db
def test_oidc_authenticate_maps_admin_group_to_workspace_admin_role(oidc_request):
    workspace = WorkspaceFactory(slug="kallistomed")
    provider = build_provider(
        request=oidc_request,
        configuration=oidc_configuration_with_access_and_workspace(admin_group="/plane/admin"),
    )
    apply_user_payload(
        provider=provider,
        email="admin-user@plane.so",
        provider_id="kc-user-admin",
        groups=["/access/plane", "/plane/admin"],
    )

    with patch.object(provider, "set_token_data"), patch.object(provider, "set_user_data"):
        user = provider.authenticate()

    workspace_member = WorkspaceMember.objects.get(workspace=workspace, member=user)

    assert workspace_member.role == 20
    assert workspace_member.is_active is True


@pytest.mark.unit
@pytest.mark.django_db
def test_oidc_authenticate_maps_guest_group_to_workspace_guest_role(oidc_request):
    workspace = WorkspaceFactory(slug="kallistomed")
    provider = build_provider(
        request=oidc_request,
        configuration=oidc_configuration_with_access_and_workspace(guest_group="/plane/viewer"),
    )
    apply_user_payload(
        provider=provider,
        email="guest-user@plane.so",
        provider_id="kc-user-guest",
        groups=["/access/plane", "/plane/viewer"],
    )

    with patch.object(provider, "set_token_data"), patch.object(provider, "set_user_data"):
        user = provider.authenticate()

    workspace_member = WorkspaceMember.objects.get(workspace=workspace, member=user)

    assert workspace_member.role == 5


@pytest.mark.unit
@pytest.mark.django_db
def test_oidc_authenticate_prefers_highest_workspace_role_when_multiple_groups(oidc_request):
    workspace = WorkspaceFactory(slug="kallistomed")
    provider = build_provider(
        request=oidc_request,
        configuration=oidc_configuration_with_access_and_workspace(
            admin_group="/plane/admin",
            member_group="/plane/member",
            guest_group="/plane/viewer",
        ),
    )
    apply_user_payload(
        provider=provider,
        email="multi-role-user@plane.so",
        provider_id="kc-user-multi-role",
        groups=["/access/plane", "/plane/viewer", "/plane/member", "/plane/admin"],
    )

    with patch.object(provider, "set_token_data"), patch.object(provider, "set_user_data"):
        user = provider.authenticate()

    workspace_member = WorkspaceMember.objects.get(workspace=workspace, member=user)

    assert workspace_member.role == 20


@pytest.mark.unit
@pytest.mark.django_db
def test_oidc_authenticate_rejects_inactive_existing_workspace_membership(oidc_request):
    workspace = WorkspaceFactory(slug="kallistomed")
    provider = build_provider(
        request=oidc_request,
        configuration=oidc_configuration_with_access_and_workspace(admin_group="/plane/admin"),
    )
    apply_user_payload(
        provider=provider,
        email="existing-member@plane.so",
        provider_id="kc-user-existing-member",
        groups=["/access/plane", "/plane/admin"],
    )

    user = provider.complete_login_or_signup()
    WorkspaceMember.objects.create(
        workspace=workspace,
        member=user,
        role=5,
        is_active=False,
    )

    with patch.object(provider, "set_token_data"), patch.object(provider, "set_user_data"):
        with pytest.raises(AuthenticationException) as exc_info:
            provider.authenticate()

    workspace_member = WorkspaceMember.objects.get(workspace=workspace, member=user)

    assert exc_info.value.error_message == "OIDC_USER_NOT_ALLOWED"
    assert workspace_member.role == 5
    assert workspace_member.is_active is False


@pytest.mark.unit
@pytest.mark.django_db
def test_oidc_authenticate_rolls_back_partial_artifacts_when_account_persistence_fails(oidc_request):
    workspace = WorkspaceFactory(slug="kallistomed")
    provider = build_provider(
        request=oidc_request,
        configuration=oidc_configuration_with_access_and_workspace(admin_group="/plane/admin"),
    )
    apply_user_payload(
        provider=provider,
        email="rollback-user@plane.so",
        provider_id="kc-user-rollback",
        groups=["/access/plane", "/plane/admin"],
    )

    with patch.object(provider, "set_token_data"), patch.object(provider, "set_user_data"), patch(
        "plane.authentication.adapter.oauth.Account.objects.create",
        side_effect=IntegrityError("duplicate-account"),
    ), pytest.raises(AuthenticationException) as exc_info:
        provider.authenticate()

    assert exc_info.value.error_message == "OIDC_OAUTH_PROVIDER_ERROR"
    assert User.objects.filter(email="rollback-user@plane.so").exists() is False
    assert Profile.objects.filter(user__email="rollback-user@plane.so").exists() is False
    assert WorkspaceMember.objects.filter(workspace=workspace, member__email="rollback-user@plane.so").exists() is False
    assert Account.objects.filter(provider_account_id="kc-user-rollback").exists() is False
