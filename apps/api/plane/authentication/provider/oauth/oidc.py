# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import os
from datetime import datetime, timedelta
from hashlib import sha256
from urllib.parse import urlencode

import pytz
import jwt
import requests
from jwt import InvalidTokenError, PyJWKClient

# Django imports
from django.core.cache import cache
from django.db import DatabaseError, IntegrityError, transaction

# Module imports
from plane.authentication.adapter.error import (
    AUTHENTICATION_ERROR_CODES,
    AuthenticationException,
)
from plane.authentication.adapter.oauth import OauthAdapter
from plane.db.models import Account, Profile, Workspace, WorkspaceMember
from plane.license.utils.instance_value import get_configuration_value


class OIDCOAuthProvider(OauthAdapter):
    provider = "oidc"
    default_scope = "openid profile email"
    default_redirect_path = "/auth/oidc/callback/"
    default_profile_language = "ru"
    discovery_timeout = 10
    discovery_cache_ttl = 3600
    request_timeout = 10

    def __init__(
        self,
        request,
        code=None,
        state=None,
        callback=None,
        redirect_path=None,
        nonce=None,
        expected_nonce=None,
    ):
        (
            OIDC_ISSUER,
            OIDC_CLIENT_ID,
            OIDC_CLIENT_SECRET,
            OIDC_SCOPE,
            OIDC_EMAIL_CLAIM,
            OIDC_FIRST_NAME_CLAIM,
            OIDC_LAST_NAME_CLAIM,
            OIDC_UID_CLAIM,
            OIDC_GROUPS_CLAIM,
            OIDC_PROVIDER_NAME,
            IS_OIDC_ENABLED,
            OIDC_REQUIRE_VERIFIED_EMAIL,
            OIDC_ACCESS_GROUP,
            OIDC_ADMIN_GROUP,
            OIDC_MEMBER_GROUP,
            OIDC_GUEST_GROUP,
            OIDC_DEFAULT_WORKSPACE_SLUG,
        ) = get_configuration_value(
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
                    "key": "OIDC_SCOPE",
                    "default": os.environ.get("OIDC_SCOPE", self.default_scope),
                },
                {
                    "key": "OIDC_EMAIL_CLAIM",
                    "default": os.environ.get("OIDC_EMAIL_CLAIM", "email"),
                },
                {
                    "key": "OIDC_FIRST_NAME_CLAIM",
                    "default": os.environ.get("OIDC_FIRST_NAME_CLAIM", "given_name"),
                },
                {
                    "key": "OIDC_LAST_NAME_CLAIM",
                    "default": os.environ.get("OIDC_LAST_NAME_CLAIM", "family_name"),
                },
                {
                    "key": "OIDC_UID_CLAIM",
                    "default": os.environ.get("OIDC_UID_CLAIM", "sub"),
                },
                {
                    "key": "OIDC_GROUPS_CLAIM",
                    "default": os.environ.get("OIDC_GROUPS_CLAIM", "groups"),
                },
                {
                    "key": "OIDC_PROVIDER_NAME",
                    "default": os.environ.get("OIDC_PROVIDER_NAME", "OpenID Connect"),
                },
                {
                    "key": "IS_OIDC_ENABLED",
                    "default": os.environ.get(
                        "IS_OIDC_ENABLED",
                        "1"
                        if os.environ.get("OIDC_ISSUER")
                        and os.environ.get("OIDC_CLIENT_ID")
                        and os.environ.get("OIDC_CLIENT_SECRET")
                        else "0",
                    ),
                },
                {
                    "key": "OIDC_REQUIRE_VERIFIED_EMAIL",
                    "default": os.environ.get("OIDC_REQUIRE_VERIFIED_EMAIL", "1"),
                },
                {
                    "key": "OIDC_ACCESS_GROUP",
                    "default": os.environ.get("OIDC_ACCESS_GROUP", ""),
                },
                {
                    "key": "OIDC_ADMIN_GROUP",
                    "default": os.environ.get("OIDC_ADMIN_GROUP", ""),
                },
                {
                    "key": "OIDC_MEMBER_GROUP",
                    "default": os.environ.get("OIDC_MEMBER_GROUP", ""),
                },
                {
                    "key": "OIDC_GUEST_GROUP",
                    "default": os.environ.get("OIDC_GUEST_GROUP", ""),
                },
                {
                    "key": "OIDC_DEFAULT_WORKSPACE_SLUG",
                    "default": os.environ.get("OIDC_DEFAULT_WORKSPACE_SLUG", ""),
                },
            ]
        )

        if IS_OIDC_ENABLED != "1" or not (OIDC_ISSUER and OIDC_CLIENT_ID and OIDC_CLIENT_SECRET):
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_NOT_CONFIGURED"],
                error_message="OIDC_NOT_CONFIGURED",
            )

        self.issuer = OIDC_ISSUER.rstrip("/")
        self.scope = (OIDC_SCOPE or self.default_scope).strip()
        self.email_claim = OIDC_EMAIL_CLAIM or "email"
        self.first_name_claim = OIDC_FIRST_NAME_CLAIM or "given_name"
        self.last_name_claim = OIDC_LAST_NAME_CLAIM or "family_name"
        self.uid_claim = OIDC_UID_CLAIM or "sub"
        self.groups_claim = OIDC_GROUPS_CLAIM or "groups"
        self.provider_name = OIDC_PROVIDER_NAME or "OpenID Connect"
        self.require_verified_email = OIDC_REQUIRE_VERIFIED_EMAIL != "0"
        self.access_group = (OIDC_ACCESS_GROUP or "").strip()
        self.admin_group = (OIDC_ADMIN_GROUP or "").strip()
        self.member_group = (OIDC_MEMBER_GROUP or "").strip()
        self.guest_group = (OIDC_GUEST_GROUP or "").strip()
        self.default_workspace_slug = (OIDC_DEFAULT_WORKSPACE_SLUG or "").strip()
        self.redirect_path = redirect_path or self.default_redirect_path
        self.nonce = nonce
        self.expected_nonce = expected_nonce

        if not self.access_group:
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_NOT_CONFIGURED"],
                error_message="OIDC_NOT_CONFIGURED",
            )

        discovery_document = self.get_discovery_document()
        auth_url = discovery_document.get("authorization_endpoint")
        token_url = discovery_document.get("token_endpoint")
        userinfo_url = discovery_document.get("userinfo_endpoint")
        jwks_uri = discovery_document.get("jwks_uri")

        if not (auth_url and token_url and userinfo_url and jwks_uri):
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_NOT_CONFIGURED"],
                error_message="OIDC_NOT_CONFIGURED",
            )

        self.discovery_document = discovery_document
        self.end_session_endpoint = discovery_document.get("end_session_endpoint")
        self.jwks_uri = jwks_uri

        client_id = OIDC_CLIENT_ID
        client_secret = OIDC_CLIENT_SECRET
        redirect_uri = (
            f"""{"https" if request.is_secure() else "http"}://{request.get_host()}{self.redirect_path}"""
        )
        url_params = {
            "client_id": client_id,
            "scope": self.scope,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "state": state,
        }
        if nonce:
            url_params["nonce"] = nonce
        auth_url = f"{auth_url}?{urlencode(url_params)}"

        super().__init__(
            request,
            self.provider,
            client_id,
            self.scope,
            redirect_uri,
            auth_url,
            token_url,
            userinfo_url,
            client_secret,
            code,
            callback=callback,
        )

    def get_discovery_document(self):
        cache_key = f"authentication.oidc.discovery.{sha256(self.issuer.encode()).hexdigest()}"
        cached_document = cache.get(cache_key)
        if cached_document:
            return cached_document

        try:
            response = requests.get(
                f"{self.issuer}/.well-known/openid-configuration",
                timeout=self.discovery_timeout,
            )
            response.raise_for_status()
            discovery_document = response.json()
            cache.set(cache_key, discovery_document, timeout=self.discovery_cache_ttl)
            return discovery_document
        except (requests.RequestException, ValueError):
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_NOT_CONFIGURED"],
                error_message="OIDC_NOT_CONFIGURED",
            )

    def set_token_data(self):
        data = {
            "code": self.code,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "redirect_uri": self.redirect_uri,
            "grant_type": "authorization_code",
        }
        token_response = self.get_user_token(data=data, headers={"Accept": "application/json"})
        self._validate_id_token(token_response=token_response)
        access_token_expires_in = token_response.get("expires_in")
        refresh_token_expires_in = token_response.get("refresh_expires_in") or token_response.get(
            "refresh_token_expires_in"
        )

        super().set_token_data(
            {
                "access_token": token_response.get("access_token"),
                "refresh_token": token_response.get("refresh_token", None),
                "access_token_expired_at": (
                    datetime.now(tz=pytz.utc) + timedelta(seconds=access_token_expires_in)
                    if access_token_expires_in
                    else None
                ),
                "refresh_token_expired_at": (
                    datetime.now(tz=pytz.utc) + timedelta(seconds=refresh_token_expires_in)
                    if refresh_token_expires_in
                    else None
                ),
                "id_token": "",
            }
        )

    def _get_claim(self, payload, claim_name, default=None):
        if not claim_name:
            return default
        return payload.get(claim_name, default)

    def _normalize_groups(self, groups):
        if groups is None:
            return []
        if isinstance(groups, str):
            return [groups]
        if isinstance(groups, (list, tuple, set)):
            return [str(group) for group in groups if group]
        return []

    def _normalize_bool_claim(self, value):
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "on"}
        return bool(value)

    def _validate_id_token(self, token_response):
        id_token = token_response.get("id_token")
        if not id_token:
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_OAUTH_PROVIDER_ERROR"],
                error_message="OIDC_OAUTH_PROVIDER_ERROR",
            )

        try:
            jwk_client = PyJWKClient(
                self.jwks_uri,
                cache_keys=True,
                cache_jwk_set=True,
                lifespan=self.discovery_cache_ttl,
                timeout=self.request_timeout,
            )
            signing_key = jwk_client.get_signing_key_from_jwt(id_token)
            token_claims = jwt.decode(
                id_token,
                signing_key.key,
                algorithms=[signing_key.algorithm_name],
                audience=self.client_id,
                issuer=self.issuer,
                options={"require": ["exp", "iat", "iss", "aud"]},
            )
        except (InvalidTokenError, jwt.PyJWTError, requests.RequestException, ValueError):
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_OAUTH_PROVIDER_ERROR"],
                error_message="OIDC_OAUTH_PROVIDER_ERROR",
            )
        audience = token_claims.get("aud")
        if isinstance(audience, list) and len(audience) > 1 and token_claims.get("azp") != self.client_id:
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_OAUTH_PROVIDER_ERROR"],
                error_message="OIDC_OAUTH_PROVIDER_ERROR",
            )

        if self.expected_nonce and token_claims.get("nonce") != self.expected_nonce:
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_OAUTH_PROVIDER_ERROR"],
                error_message="OIDC_OAUTH_PROVIDER_ERROR",
            )
        self.id_token_claims = token_claims

    def get_provider_instance(self):
        return self.issuer

    def _ensure_no_provider_instance_conflict(self, provider_id):
        if not provider_id:
            return
        conflict_exists = (
            Account.objects.filter(provider=self.provider, provider_account_id=str(provider_id))
            .exclude(provider_instance=self.get_provider_instance())
            .exists()
        )
        if conflict_exists:
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_PROVIDER_INSTANCE_CONFLICT"],
                error_message="OIDC_PROVIDER_INSTANCE_CONFLICT",
            )

    def get_existing_user(self, email):
        provider_id = self.user_data.get("user", {}).get("provider_id")
        if provider_id:
            self._ensure_no_provider_instance_conflict(provider_id)
            account = (
                Account.objects.select_related("user")
                .filter(
                    provider=self.provider,
                    provider_instance=self.get_provider_instance(),
                    provider_account_id=str(provider_id),
                )
                .first()
            )
            if account:
                self._ensure_existing_user_allowed(account.user)
                return account.user

        user = super().get_existing_user(email=email)
        if user:
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_ACCOUNT_LINK_CONFLICT"],
                error_message="OIDC_ACCOUNT_LINK_CONFLICT",
            )
        return None

    def authenticate(self):
        try:
            with transaction.atomic():
                self.set_token_data()
                self.set_user_data()
                self._enforce_verified_email()
                self._enforce_access_group()
                workspace = self._get_default_workspace()
                email = self.sanitize_email(self.user_data.get("email"))
                is_new_user = self.get_existing_user(email=email) is None
                user = self.complete_login_or_signup()
                self._ensure_default_workspace_membership(user=user, workspace=workspace)
                self._sync_oidc_profile(
                    user=user,
                    workspace=workspace,
                    set_default_language=is_new_user,
                )
                return user
        except AuthenticationException:
            raise
        except (DatabaseError, IntegrityError) as exc:
            self.logger.warning(
                "Error completing OIDC authentication flow",
                extra={"provider": self.provider, "provider_instance": self.get_provider_instance()},
            )
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_OAUTH_PROVIDER_ERROR"],
                error_message="OIDC_OAUTH_PROVIDER_ERROR",
            ) from exc

    def complete_login_or_signup(self):
        self._enforce_verified_email()
        return super().complete_login_or_signup()

    def save_user_data(self, user):
        self._ensure_existing_user_allowed(user)
        return super().save_user_data(user=user)

    def _ensure_existing_user_allowed(self, user):
        if user and not user.is_active:
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["USER_ACCOUNT_DEACTIVATED"],
                error_message="USER_ACCOUNT_DEACTIVATED",
            )

    def _enforce_verified_email(self):
        if not self.require_verified_email:
            return
        if self.user_data.get("email_verified") is not True:
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_EMAIL_NOT_VERIFIED"],
                error_message="OIDC_EMAIL_NOT_VERIFIED",
            )

    def _enforce_access_group(self):
        if self.access_group not in self.user_data.get("groups", []):
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_USER_NOT_ALLOWED"],
                error_message="OIDC_USER_NOT_ALLOWED",
            )

    def _get_default_workspace(self):
        if not self.default_workspace_slug:
            return None

        workspace = Workspace.objects.filter(slug=self.default_workspace_slug).first()
        if not workspace:
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_DEFAULT_WORKSPACE_NOT_FOUND"],
                error_message="OIDC_DEFAULT_WORKSPACE_NOT_FOUND",
            )
        return workspace

    def _get_workspace_role(self):
        groups = set(self.user_data.get("groups", []))

        if self.admin_group and self.admin_group in groups:
            return 20
        if self.member_group and self.member_group in groups:
            return 15
        if self.guest_group and self.guest_group in groups:
            return 5

        # If the user passed access gating but no role-specific group matched,
        # default to Member so the login flow remains usable.
        return 15

    def _ensure_default_workspace_membership(self, user, workspace=None):
        if not workspace:
            return

        workspace_role = self._get_workspace_role()

        member, created = WorkspaceMember.objects.get_or_create(
            workspace=workspace,
            member=user,
            defaults={
                "role": workspace_role,
                "is_active": True,
            },
        )
        if not created:
            if not member.is_active:
                raise AuthenticationException(
                    error_code=AUTHENTICATION_ERROR_CODES["OIDC_USER_NOT_ALLOWED"],
                    error_message="OIDC_USER_NOT_ALLOWED",
                )
            update_fields = []
            if member.role != workspace_role:
                member.role = workspace_role
                update_fields.append("role")
            if update_fields:
                member.save(update_fields=update_fields)

    def _completed_onboarding_step(self):
        return {
            "profile_complete": True,
            "workspace_create": True,
            "workspace_invite": True,
            "workspace_join": True,
        }

    def _completed_mobile_onboarding_step(self):
        return {
            "profile_complete": True,
            "workspace_create": True,
            "workspace_join": True,
        }

    def _sync_oidc_profile(self, user, workspace=None, set_default_language=False):
        profile, _ = Profile.objects.get_or_create(user=user)
        update_fields = []

        if workspace and profile.last_workspace_id != workspace.id:
            profile.last_workspace_id = workspace.id
            update_fields.append("last_workspace_id")

        completed_onboarding_step = self._completed_onboarding_step()
        if profile.onboarding_step != completed_onboarding_step:
            profile.onboarding_step = completed_onboarding_step
            update_fields.append("onboarding_step")

        if not profile.is_onboarded:
            profile.is_onboarded = True
            update_fields.append("is_onboarded")

        completed_mobile_onboarding_step = self._completed_mobile_onboarding_step()
        if profile.mobile_onboarding_step != completed_mobile_onboarding_step:
            profile.mobile_onboarding_step = completed_mobile_onboarding_step
            update_fields.append("mobile_onboarding_step")

        if not profile.is_mobile_onboarded:
            profile.is_mobile_onboarded = True
            update_fields.append("is_mobile_onboarded")

        if not profile.is_tour_completed:
            profile.is_tour_completed = True
            update_fields.append("is_tour_completed")

        if set_default_language and profile.language != self.default_profile_language:
            profile.language = self.default_profile_language
            update_fields.append("language")

        if update_fields:
            profile.save(update_fields=update_fields)

    def set_user_data(self):
        user_info_response = self.get_user_response()
        provider_id = self._get_claim(user_info_response, self.uid_claim)
        if not provider_id:
            raise AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_OAUTH_PROVIDER_ERROR"],
                error_message="OIDC_OAUTH_PROVIDER_ERROR",
            )

        email = self._get_claim(user_info_response, self.email_claim)
        email_verified = self._normalize_bool_claim(user_info_response.get("email_verified"))
        display_name = user_info_response.get("preferred_username") or user_info_response.get("name") or ""
        groups = self._normalize_groups(self._get_claim(user_info_response, self.groups_claim, []))

        super().set_user_data(
            {
                "email": email,
                "email_verified": email_verified,
                "groups": groups,
                "provider_name": self.provider_name,
                "user": {
                    "provider_id": str(provider_id),
                    "avatar": user_info_response.get("picture", ""),
                    "display_name": display_name,
                    "first_name": self._get_claim(user_info_response, self.first_name_claim, ""),
                    "last_name": self._get_claim(user_info_response, self.last_name_claim, ""),
                    "is_password_autoset": True,
                },
            }
        )
