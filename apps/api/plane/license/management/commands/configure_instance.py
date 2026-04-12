# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import os

# Django imports
from django.core.management.base import BaseCommand, CommandError

# Module imports
from plane.license.models import InstanceConfiguration
from plane.utils.instance_config_variables import instance_config_variables


class Command(BaseCommand):
    help = "Configure instance variables"

    def _create_auth_enabled_configuration(self, key, value):
        obj = InstanceConfiguration.objects.create(
            key=key,
            value=value,
            category="AUTHENTICATION",
            is_encrypted=False,
        )
        self.stdout.write(self.style.SUCCESS(f"{obj.key} loaded with value from environment variable."))

    def _oidc_enabled_value(self):
        from plane.license.utils.instance_value import get_configuration_value

        OIDC_ISSUER, OIDC_CLIENT_ID, OIDC_CLIENT_SECRET, OIDC_ACCESS_GROUP = get_configuration_value(
            [
                {
                    "key": "OIDC_ISSUER",
                    "default": os.environ.get("OIDC_ISSUER", ""),
                },
                {
                    "key": "OIDC_CLIENT_ID",
                    "default": os.environ.get("OIDC_CLIENT_ID", ""),
                },
                {
                    "key": "OIDC_CLIENT_SECRET",
                    "default": os.environ.get("OIDC_CLIENT_SECRET", ""),
                },
                {
                    "key": "OIDC_ACCESS_GROUP",
                    "default": os.environ.get("OIDC_ACCESS_GROUP", ""),
                },
            ]
        )
        return "1" if bool(OIDC_ISSUER) and bool(OIDC_CLIENT_ID) and bool(OIDC_CLIENT_SECRET) and bool(OIDC_ACCESS_GROUP) else "0"

    def handle(self, *args, **options):
        from plane.license.utils.encryption import encrypt_data
        from plane.license.utils.instance_value import get_configuration_value

        mandatory_keys = ["SECRET_KEY"]

        for item in mandatory_keys:
            if not os.environ.get(item):
                raise CommandError(f"{item} env variable is required.")

        for item in instance_config_variables:
            obj, created = InstanceConfiguration.objects.get_or_create(key=item.get("key"))
            if created:
                obj.category = item.get("category")
                obj.is_encrypted = item.get("is_encrypted", False)
                if item.get("is_encrypted", False):
                    obj.value = encrypt_data(item.get("value"))
                else:
                    obj.value = item.get("value")
                obj.save()
                self.stdout.write(self.style.SUCCESS(f"{obj.key} loaded with value from environment variable."))
            else:
                self.stdout.write(self.style.WARNING(f"{obj.key} configuration already exists"))

        keys = [
            "IS_GOOGLE_ENABLED",
            "IS_GITHUB_ENABLED",
            "IS_GITLAB_ENABLED",
            "IS_GITEA_ENABLED",
            "IS_OIDC_ENABLED",
        ]
        for key in keys:
            if InstanceConfiguration.objects.filter(key=key).exists():
                self.stdout.write(self.style.WARNING(f"{key} configuration already exists"))
                continue
            if key == "IS_GOOGLE_ENABLED":
                GOOGLE_CLIENT_ID, GOOGLE_CLIENT_SECRET = get_configuration_value(
                    [
                        {
                            "key": "GOOGLE_CLIENT_ID",
                            "default": os.environ.get("GOOGLE_CLIENT_ID", ""),
                        },
                        {
                            "key": "GOOGLE_CLIENT_SECRET",
                            "default": os.environ.get("GOOGLE_CLIENT_SECRET", "0"),
                        },
                    ]
                )
                value = "1" if bool(GOOGLE_CLIENT_ID) and bool(GOOGLE_CLIENT_SECRET) else "0"
                self._create_auth_enabled_configuration(key=key, value=value)
            if key == "IS_GITHUB_ENABLED":
                GITHUB_CLIENT_ID, GITHUB_CLIENT_SECRET = get_configuration_value(
                    [
                        {
                            "key": "GITHUB_CLIENT_ID",
                            "default": os.environ.get("GITHUB_CLIENT_ID", ""),
                        },
                        {
                            "key": "GITHUB_CLIENT_SECRET",
                            "default": os.environ.get("GITHUB_CLIENT_SECRET", "0"),
                        },
                    ]
                )
                value = "1" if bool(GITHUB_CLIENT_ID) and bool(GITHUB_CLIENT_SECRET) else "0"
                self._create_auth_enabled_configuration(key=key, value=value)
            if key == "IS_GITLAB_ENABLED":
                GITLAB_HOST, GITLAB_CLIENT_ID, GITLAB_CLIENT_SECRET = get_configuration_value(
                    [
                        {
                            "key": "GITLAB_HOST",
                            "default": os.environ.get("GITLAB_HOST", "https://gitlab.com"),
                        },
                        {
                            "key": "GITLAB_CLIENT_ID",
                            "default": os.environ.get("GITLAB_CLIENT_ID", ""),
                        },
                        {
                            "key": "GITLAB_CLIENT_SECRET",
                            "default": os.environ.get("GITLAB_CLIENT_SECRET", ""),
                        },
                    ]
                )
                value = "1" if bool(GITLAB_HOST) and bool(GITLAB_CLIENT_ID) and bool(GITLAB_CLIENT_SECRET) else "0"
                self._create_auth_enabled_configuration(key=key, value=value)
            if key == "IS_GITEA_ENABLED":
                GITEA_HOST, GITEA_CLIENT_ID, GITEA_CLIENT_SECRET = get_configuration_value(
                    [
                        {
                            "key": "GITEA_HOST",
                            "default": os.environ.get("GITEA_HOST", ""),
                        },
                        {
                            "key": "GITEA_CLIENT_ID",
                            "default": os.environ.get("GITEA_CLIENT_ID", ""),
                        },
                        {
                            "key": "GITEA_CLIENT_SECRET",
                            "default": os.environ.get("GITEA_CLIENT_SECRET", ""),
                        },
                    ]
                )
                value = "1" if bool(GITEA_HOST) and bool(GITEA_CLIENT_ID) and bool(GITEA_CLIENT_SECRET) else "0"
                self._create_auth_enabled_configuration(key=key, value=value)
            if key == "IS_OIDC_ENABLED":
                self._create_auth_enabled_configuration(key=key, value=self._oidc_enabled_value())
