# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

import copy
from datetime import timedelta
import re
import zoneinfo

from django.core.exceptions import ObjectDoesNotExist
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError


DYNAMIC_FILTER_TOKEN_CURRENT_USER = "current_user"
DYNAMIC_FILTER_TOKEN_TODAY = "today"
DYNAMIC_FILTER_TOKEN_END_OF_WEEK = "end_of_week"

_TOKEN_ALIASES = {
    DYNAMIC_FILTER_TOKEN_CURRENT_USER: DYNAMIC_FILTER_TOKEN_CURRENT_USER,
    "currentUser()": DYNAMIC_FILTER_TOKEN_CURRENT_USER,
    DYNAMIC_FILTER_TOKEN_TODAY: DYNAMIC_FILTER_TOKEN_TODAY,
    "today()": DYNAMIC_FILTER_TOKEN_TODAY,
    DYNAMIC_FILTER_TOKEN_END_OF_WEEK: DYNAMIC_FILTER_TOKEN_END_OF_WEEK,
    "endOfWeek()": DYNAMIC_FILTER_TOKEN_END_OF_WEEK,
}

_DATE_TOKENS = {DYNAMIC_FILTER_TOKEN_TODAY, DYNAMIC_FILTER_TOKEN_END_OF_WEEK}
_USER_TOKENS = {DYNAMIC_FILTER_TOKEN_CURRENT_USER}
_KNOWN_TOKENS = _DATE_TOKENS | _USER_TOKENS

_USER_TOKEN_FIELDS = {"assignee_id", "created_by_id", "mention_id", "subscriber_id"}
_USER_TOKEN_OPERATORS = {"exact", "in"}
_DATE_TOKEN_FIELDS = {"start_date", "target_date", "created_at", "updated_at"}
_DATE_TOKEN_OPERATORS = {"exact", "range", "lte"}
_FUNCTION_TOKEN_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*\(\)$")


def resolve_dynamic_filter_values(request, filter_data):
    """Return a request-local copy of filter_data with supported dynamic tokens resolved."""
    resolved_filter_data = copy.deepcopy(filter_data)
    context = _DynamicFilterContext(request)
    return _resolve_node(context, resolved_filter_data)


class _DynamicFilterContext:
    def __init__(self, request):
        self.request = request
        self._today = None
        self._end_of_week = None

    @property
    def current_user_id(self):
        user = getattr(self.request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            _raise_dynamic_filter_error("current_user requires an authenticated request user")
        return str(user.id)

    @property
    def today(self):
        if self._today is None:
            self._today = timezone.now().astimezone(self._get_timezone()).date()
        return self._today

    @property
    def end_of_week(self):
        if self._end_of_week is None:
            self._end_of_week = self.today + timedelta(days=self._days_until_week_end())
        return self._end_of_week

    def _get_timezone(self):
        user = getattr(self.request, "user", None)
        timezone_name = getattr(user, "user_timezone", None) or "UTC"
        try:
            return zoneinfo.ZoneInfo(timezone_name)
        except zoneinfo.ZoneInfoNotFoundError:
            return zoneinfo.ZoneInfo("UTC")

    def _days_until_week_end(self):
        start_of_week = self._get_start_of_week()
        python_start_weekday = (start_of_week + 6) % 7
        python_end_weekday = (python_start_weekday + 6) % 7
        return (python_end_weekday - self.today.weekday()) % 7

    def _get_start_of_week(self):
        user = getattr(self.request, "user", None)
        try:
            profile = getattr(user, "profile", None)
        except (AttributeError, ObjectDoesNotExist):
            profile = None

        start_of_week = getattr(profile, "start_of_the_week", None)
        if isinstance(start_of_week, int) and 0 <= start_of_week <= 6:
            return start_of_week

        return 1


def _resolve_node(context, node):
    if not isinstance(node, dict):
        return node

    for key, value in list(node.items()):
        if isinstance(key, str) and key.lower() in ("or", "and"):
            node[key] = [_resolve_node(context, child) for child in value]
            continue

        if isinstance(key, str) and key.lower() == "not":
            node[key] = _resolve_node(context, value)
            continue

        node[key] = _resolve_leaf_value(context, key, value)

    return node


def _resolve_leaf_value(context, field_lookup, value):
    field_name, operator = _split_field_lookup(field_lookup)

    if isinstance(value, list):
        return [_resolve_scalar_value(context, field_name, operator, item) for item in value]

    if isinstance(value, tuple):
        return tuple(_resolve_scalar_value(context, field_name, operator, item) for item in value)

    if isinstance(value, str) and operator in ("in", "range") and "," in value:
        resolved_parts = [
            _resolve_scalar_value(context, field_name, operator, item.strip()) for item in value.split(",")
        ]
        return ",".join(str(item) for item in resolved_parts)

    return _resolve_scalar_value(context, field_name, operator, value)


def _resolve_scalar_value(context, field_name, operator, value):
    if not isinstance(value, str):
        return value

    token = _TOKEN_ALIASES.get(value)
    if not token:
        if _FUNCTION_TOKEN_PATTERN.match(value):
            _raise_dynamic_filter_error(f"Unsupported dynamic filter token '{value}'")
        return value

    _validate_token_usage(token, field_name, operator)

    if token == DYNAMIC_FILTER_TOKEN_CURRENT_USER:
        return context.current_user_id

    if token == DYNAMIC_FILTER_TOKEN_TODAY:
        return context.today.isoformat()

    if token == DYNAMIC_FILTER_TOKEN_END_OF_WEEK:
        return context.end_of_week.isoformat()

    _raise_dynamic_filter_error(f"Unsupported dynamic filter token '{value}'")


def _validate_token_usage(token, field_name, operator):
    if token in _USER_TOKENS and field_name in _USER_TOKEN_FIELDS and operator in _USER_TOKEN_OPERATORS:
        return

    if token in _DATE_TOKENS and field_name in _DATE_TOKEN_FIELDS and operator in _DATE_TOKEN_OPERATORS:
        return

    if token in _KNOWN_TOKENS:
        _raise_dynamic_filter_error(
            f"Dynamic filter token '{token}' is not supported for '{field_name}__{operator}'"
        )


def _split_field_lookup(field_lookup):
    if not isinstance(field_lookup, str):
        return field_lookup, "exact"

    if "__" not in field_lookup:
        return field_lookup, "exact"

    field_name, operator = field_lookup.rsplit("__", 1)
    return field_name, operator


def _raise_dynamic_filter_error(message):
    raise DRFValidationError({"message": message, "code": "invalid_dynamic_filter_value"})
