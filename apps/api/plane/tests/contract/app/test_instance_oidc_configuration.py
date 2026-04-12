# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import pytest
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status

from plane.license.models import Instance, InstanceAdmin, InstanceConfiguration


@pytest.fixture
def configured_instance(db):
    instance, _ = Instance.objects.update_or_create(
        instance_id="oidc-test-instance",
        defaults={
            "instance_name": "OIDC Test Instance",
            "current_version": "1.0.0",
            "domain": "https://plane.example.com",
            "last_checked_at": timezone.now(),
            "is_setup_done": True,
        },
    )
    return instance


@pytest.fixture
def instance_admin_user(create_user, configured_instance):
    InstanceAdmin.objects.create(instance=configured_instance, user=create_user, role=20)
    return create_user


@pytest.mark.contract
@pytest.mark.django_db
def test_configure_instance_creates_oidc_configuration_values(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("OIDC_ISSUER", "https://auth.example.com/realms/kallistomed")
    monkeypatch.setenv("OIDC_CLIENT_ID", "plane")
    monkeypatch.setenv("OIDC_CLIENT_SECRET", "secret-value")
    monkeypatch.setenv("OIDC_PROVIDER_NAME", "Keycloak")
    monkeypatch.setenv("OIDC_ACCESS_GROUP", "/access/plane")

    call_command("configure_instance")

    values = {
        item.key: item.value
        for item in InstanceConfiguration.objects.filter(
            key__in=[
                "IS_OIDC_ENABLED",
                "OIDC_PROVIDER_NAME",
                "OIDC_ISSUER",
                "OIDC_CLIENT_ID",
                "OIDC_SCOPE",
                "OIDC_UID_CLAIM",
                "OIDC_GROUPS_CLAIM",
                "OIDC_REQUIRE_VERIFIED_EMAIL",
                "OIDC_ACCESS_GROUP",
            ]
        )
    }

    assert values["IS_OIDC_ENABLED"] == "1"
    assert values["OIDC_PROVIDER_NAME"] == "Keycloak"
    assert values["OIDC_ISSUER"] == "https://auth.example.com/realms/kallistomed"
    assert values["OIDC_CLIENT_ID"] == "plane"
    assert values["OIDC_SCOPE"] == "openid profile email"
    assert values["OIDC_UID_CLAIM"] == "sub"
    assert values["OIDC_GROUPS_CLAIM"] == "groups"
    assert values["OIDC_REQUIRE_VERIFIED_EMAIL"] == "1"
    assert values["OIDC_ACCESS_GROUP"] == "/access/plane"


@pytest.mark.contract
@pytest.mark.django_db
@override_settings(SKIP_ENV_VAR=True)
def test_instance_endpoint_returns_is_oidc_enabled(api_client, configured_instance):
    InstanceConfiguration.objects.create(key="IS_OIDC_ENABLED", value="1", category="AUTHENTICATION")

    response = api_client.get(reverse("instance"))

    assert response.status_code == status.HTTP_200_OK
    assert response.data["config"]["is_oidc_enabled"] is True


@pytest.mark.contract
@pytest.mark.django_db
def test_instance_configuration_round_trip_updates_oidc_values(api_client, configured_instance, instance_admin_user):
    for key, value, category, is_encrypted in [
        ("IS_OIDC_ENABLED", "0", "AUTHENTICATION", False),
        ("OIDC_PROVIDER_NAME", "OpenID Connect", "OIDC", False),
        ("OIDC_ISSUER", "", "OIDC", False),
        ("OIDC_CLIENT_ID", "", "OIDC", False),
        ("OIDC_CLIENT_SECRET", "", "OIDC", True),
        ("OIDC_REQUIRE_VERIFIED_EMAIL", "1", "OIDC", False),
        ("OIDC_ACCESS_GROUP", "", "OIDC", False),
    ]:
        InstanceConfiguration.objects.create(
            key=key,
            value=value,
            category=category,
            is_encrypted=is_encrypted,
        )

    api_client.force_authenticate(user=instance_admin_user)
    payload = {
        "IS_OIDC_ENABLED": "1",
        "OIDC_PROVIDER_NAME": "Keycloak",
        "OIDC_ISSUER": "https://auth.example.com/realms/kallistomed",
        "OIDC_CLIENT_ID": "plane",
        "OIDC_CLIENT_SECRET": "secret-value",
        "OIDC_REQUIRE_VERIFIED_EMAIL": "0",
        "OIDC_ACCESS_GROUP": "/access/plane",
    }

    patch_response = api_client.patch(reverse("instance-configuration"), payload, format="json")

    assert patch_response.status_code == status.HTTP_200_OK

    get_response = api_client.get(reverse("instance-configuration"))
    assert get_response.status_code == status.HTTP_200_OK

    configuration_map = {item["key"]: item["value"] for item in get_response.data}

    assert configuration_map["IS_OIDC_ENABLED"] == "1"
    assert configuration_map["OIDC_PROVIDER_NAME"] == "Keycloak"
    assert configuration_map["OIDC_ISSUER"] == "https://auth.example.com/realms/kallistomed"
    assert configuration_map["OIDC_CLIENT_ID"] == "plane"
    assert configuration_map["OIDC_CLIENT_SECRET"] == "secret-value"
    assert configuration_map["OIDC_REQUIRE_VERIFIED_EMAIL"] == "0"
    assert configuration_map["OIDC_ACCESS_GROUP"] == "/access/plane"


@pytest.mark.contract
@pytest.mark.django_db
def test_instance_configuration_rejects_enabled_oidc_without_access_group(
    api_client, configured_instance, instance_admin_user
):
    for key, value, category, is_encrypted in [
        ("IS_OIDC_ENABLED", "0", "AUTHENTICATION", False),
        ("OIDC_ISSUER", "", "OIDC", False),
        ("OIDC_CLIENT_ID", "", "OIDC", False),
        ("OIDC_CLIENT_SECRET", "", "OIDC", True),
        ("OIDC_ACCESS_GROUP", "", "OIDC", False),
    ]:
        InstanceConfiguration.objects.create(
            key=key,
            value=value,
            category=category,
            is_encrypted=is_encrypted,
        )

    api_client.force_authenticate(user=instance_admin_user)
    payload = {
        "IS_OIDC_ENABLED": "1",
        "OIDC_ISSUER": "https://auth.example.com/realms/kallistomed",
        "OIDC_CLIENT_ID": "plane",
        "OIDC_CLIENT_SECRET": "secret-value",
        "OIDC_ACCESS_GROUP": "",
    }

    patch_response = api_client.patch(reverse("instance-configuration"), payload, format="json")

    assert patch_response.status_code == status.HTTP_400_BAD_REQUEST
    assert patch_response.data["missing_keys"] == ["OIDC_ACCESS_GROUP"]
