# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Python imports
import uuid

# Django import
from django.http import HttpResponseRedirect
from django.utils.http import url_has_allowed_host_and_scheme
from django.views import View

# Module imports
from plane.authentication.adapter.error import (
    AUTHENTICATION_ERROR_CODES,
    AuthenticationException,
)
from plane.authentication.provider.oauth.oidc import OIDCOAuthProvider
from plane.authentication.utils.host import base_host
from plane.authentication.utils.login import user_login
from plane.authentication.utils.user_auth_workflow import post_user_auth_workflow
from plane.license.models import Instance
from plane.utils.exception_logger import log_exception
from plane.utils.path_validator import get_allowed_hosts, get_safe_redirect_url, validate_next_path


SPACE_OIDC_CALLBACK_PATH = "/auth/spaces/oidc/callback/"


class OIDCOauthInitiateSpaceEndpoint(View):
    def get(self, request):
        request.session["host"] = base_host(request=request, is_space=True)
        next_path = request.GET.get("next_path")
        if next_path:
            request.session["next_path"] = str(next_path)

        instance = Instance.objects.first()
        if instance is None or not instance.is_setup_done:
            exc = AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["INSTANCE_NOT_CONFIGURED"],
                error_message="INSTANCE_NOT_CONFIGURED",
            )
            params = exc.get_error_dict()
            url = get_safe_redirect_url(
                base_url=base_host(request=request, is_space=True), next_path=next_path, params=params
            )
            return HttpResponseRedirect(url)

        try:
            state = uuid.uuid4().hex
            nonce = uuid.uuid4().hex
            provider = OIDCOAuthProvider(
                request=request,
                state=state,
                nonce=nonce,
                redirect_path=SPACE_OIDC_CALLBACK_PATH,
            )
            request.session["state"] = state
            request.session["oidc_nonce"] = nonce
            return HttpResponseRedirect(provider.get_auth_url())
        except AuthenticationException as e:
            params = e.get_error_dict()
            url = get_safe_redirect_url(
                base_url=base_host(request=request, is_space=True), next_path=next_path, params=params
            )
            return HttpResponseRedirect(url)
        except Exception as exc:
            log_exception(exc)
            params = AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_OAUTH_PROVIDER_ERROR"],
                error_message="OIDC_OAUTH_PROVIDER_ERROR",
            ).get_error_dict()
            url = get_safe_redirect_url(
                base_url=base_host(request=request, is_space=True), next_path=next_path, params=params
            )
            return HttpResponseRedirect(url)


class OIDCCallbackSpaceEndpoint(View):
    def get(self, request):
        code = request.GET.get("code")
        state = request.GET.get("state")
        space_base_url = request.session.get("host") or base_host(request=request, is_space=True)
        next_path = request.session.get("next_path")
        expected_state = request.session.get("state", "")

        if state != expected_state:
            request.session.pop("state", None)
            request.session.pop("oidc_nonce", None)
            exc = AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_OAUTH_PROVIDER_ERROR"],
                error_message="OIDC_OAUTH_PROVIDER_ERROR",
            )
            params = exc.get_error_dict()
            url = get_safe_redirect_url(base_url=space_base_url, next_path=next_path, params=params)
            return HttpResponseRedirect(url)

        if not code:
            request.session.pop("state", None)
            request.session.pop("oidc_nonce", None)
            exc = AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_OAUTH_PROVIDER_ERROR"],
                error_message="OIDC_OAUTH_PROVIDER_ERROR",
            )
            params = exc.get_error_dict()
            url = get_safe_redirect_url(base_url=space_base_url, next_path=next_path, params=params)
            return HttpResponseRedirect(url)

        try:
            expected_nonce = request.session.pop("oidc_nonce", None)
            request.session.pop("state", None)
            provider = OIDCOAuthProvider(
                request=request,
                code=code,
                callback=post_user_auth_workflow,
                redirect_path=SPACE_OIDC_CALLBACK_PATH,
                expected_nonce=expected_nonce,
            )
            user = provider.authenticate()
            user_login(request=request, user=user, is_space=True)
            validated_next_path = validate_next_path(next_path=next_path)
            url = f"{space_base_url.rstrip('/')}{validated_next_path}"
            if url_has_allowed_host_and_scheme(url, allowed_hosts=get_allowed_hosts()):
                return HttpResponseRedirect(url)
            return HttpResponseRedirect(space_base_url)
        except AuthenticationException as e:
            params = e.get_error_dict()
            url = get_safe_redirect_url(base_url=space_base_url, next_path=next_path, params=params)
            return HttpResponseRedirect(url)
        except Exception as exc:
            log_exception(exc)
            params = AuthenticationException(
                error_code=AUTHENTICATION_ERROR_CODES["OIDC_OAUTH_PROVIDER_ERROR"],
                error_message="OIDC_OAUTH_PROVIDER_ERROR",
            ).get_error_dict()
            url = get_safe_redirect_url(base_url=space_base_url, next_path=next_path, params=params)
            return HttpResponseRedirect(url)
