# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

from datetime import date, datetime, timezone as datetime_timezone
from types import SimpleNamespace

import pytest
from rest_framework.exceptions import ValidationError as DRFValidationError

from plane.db.models import Issue, IssueAssignee, Project, State, StateGroup, Workspace, WorkspaceMember
from plane.tests.factories import UserFactory
from plane.utils.filters import dynamic_values
from plane.utils.filters.dynamic_values import (
    DYNAMIC_FILTER_TOKEN_CURRENT_USER,
    DYNAMIC_FILTER_TOKEN_END_OF_WEEK,
    DYNAMIC_FILTER_TOKEN_TODAY,
    resolve_dynamic_filter_values,
)
from plane.utils.filters.filter_backend import ComplexFilterBackend
from plane.utils.filters.filterset import IssueFilterSet


class _IssueFilterView:
    filterset_class = IssueFilterSet


def _request_for(user):
    return SimpleNamespace(user=user)


def _freeze_now(monkeypatch, frozen_at):
    monkeypatch.setattr(dynamic_values.timezone, "now", lambda: frozen_at)


@pytest.mark.unit
class TestDynamicFilterValueResolver:
    def test_existing_static_assignee_and_date_filters_are_unchanged(self, db):
        user_id = "1f5d8af9-98cb-49aa-ae73-7de9c4fdc47e"
        payload = {
            "and": [
                {"assignee_id__in": user_id},
                {"target_date__exact": "2026-05-30"},
                {"start_date__range": "2026-05-01,2026-05-31"},
            ]
        }
        user = UserFactory()

        resolved = resolve_dynamic_filter_values(_request_for(user), payload)

        assert resolved == payload
        assert resolved is not payload

    def test_current_user_token_resolves_per_request_user(self, db):
        first_user = UserFactory()
        second_user = UserFactory()
        payload = {"assignee_id__in": DYNAMIC_FILTER_TOKEN_CURRENT_USER}

        first_resolved = resolve_dynamic_filter_values(_request_for(first_user), payload)
        second_resolved = resolve_dynamic_filter_values(_request_for(second_user), payload)

        assert first_resolved == {"assignee_id__in": str(first_user.id)}
        assert second_resolved == {"assignee_id__in": str(second_user.id)}
        assert payload == {"assignee_id__in": DYNAMIC_FILTER_TOKEN_CURRENT_USER}

    def test_today_and_end_of_week_resolve_in_request_user_timezone(self, db, monkeypatch):
        user = UserFactory(user_timezone="Pacific/Kiritimati")
        _freeze_now(monkeypatch, datetime(2026, 5, 29, 11, 30, tzinfo=datetime_timezone.utc))
        payload = {
            "and": [
                {"target_date__exact": DYNAMIC_FILTER_TOKEN_TODAY},
                {"target_date__lte": DYNAMIC_FILTER_TOKEN_END_OF_WEEK},
            ]
        }

        resolved = resolve_dynamic_filter_values(_request_for(user), payload)

        assert resolved == {
            "and": [
                {"target_date__exact": "2026-05-30"},
                {"target_date__lte": "2026-05-31"},
            ]
        }

    def test_end_of_week_respects_user_start_of_week(self, monkeypatch):
        user = SimpleNamespace(
            id="759b6127-7d29-41ce-9419-736cd8c07bdb",
            is_authenticated=True,
            user_timezone="UTC",
            profile=SimpleNamespace(start_of_the_week=0),
        )
        _freeze_now(monkeypatch, datetime(2026, 5, 29, 20, 0, tzinfo=datetime_timezone.utc))

        resolved = resolve_dynamic_filter_values(
            _request_for(user), {"target_date__lte": DYNAMIC_FILTER_TOKEN_END_OF_WEEK}
        )

        assert resolved == {"target_date__lte": "2026-05-30"}

    def test_date_tokens_resolve_inside_range_without_mutating_payload(self, db, monkeypatch):
        user = UserFactory(user_timezone="UTC")
        _freeze_now(monkeypatch, datetime(2026, 5, 29, 20, 0, tzinfo=datetime_timezone.utc))
        payload = {"target_date__range": [DYNAMIC_FILTER_TOKEN_TODAY, DYNAMIC_FILTER_TOKEN_END_OF_WEEK]}

        resolved = resolve_dynamic_filter_values(_request_for(user), payload)

        assert resolved == {"target_date__range": ["2026-05-29", "2026-05-31"]}
        assert payload == {"target_date__range": [DYNAMIC_FILTER_TOKEN_TODAY, DYNAMIC_FILTER_TOKEN_END_OF_WEEK]}

    def test_invalid_token_on_unsupported_field_is_rejected(self, db):
        user = UserFactory()

        with pytest.raises(DRFValidationError) as exc:
            resolve_dynamic_filter_values(_request_for(user), {"priority__exact": DYNAMIC_FILTER_TOKEN_CURRENT_USER})

        assert exc.value.detail["code"] == "invalid_dynamic_filter_value"

    def test_unknown_function_style_dynamic_token_is_rejected(self, db):
        user = UserFactory()

        with pytest.raises(DRFValidationError) as exc:
            resolve_dynamic_filter_values(_request_for(user), {"target_date__exact": "tomorrow()"})

        assert exc.value.detail["code"] == "invalid_dynamic_filter_value"


@pytest.mark.unit
class TestDynamicFiltersThroughIssueFilterBackend:
    @pytest.fixture
    def issue_filter_data(self, db):
        first_user = UserFactory()
        second_user = UserFactory()
        workspace = Workspace.objects.create(name="Dynamic Filters", slug="dynamic-filters", owner=first_user)
        WorkspaceMember.objects.create(workspace=workspace, member=first_user, role=20)
        WorkspaceMember.objects.create(workspace=workspace, member=second_user, role=20)
        project = Project.objects.create(name="Dynamic Project", identifier="DYN", workspace=workspace)
        state = State.objects.create(
            name="Backlog",
            color="#60646C",
            group=StateGroup.BACKLOG.value,
            default=True,
            project=project,
        )
        first_issue = Issue.objects.create(
            name="Assigned to first user",
            project=project,
            state=state,
            target_date=date(2026, 5, 31),
        )
        second_issue = Issue.objects.create(
            name="Assigned to second user",
            project=project,
            state=state,
            target_date=date(2026, 6, 1),
        )
        next_week_issue = Issue.objects.create(
            name="Next week",
            project=project,
            state=state,
            target_date=date(2026, 6, 2),
        )
        IssueAssignee.objects.create(project=project, issue=first_issue, assignee=first_user)
        IssueAssignee.objects.create(project=project, issue=second_issue, assignee=second_user)

        return {
            "first_user": first_user,
            "second_user": second_user,
            "first_issue": first_issue,
            "second_issue": second_issue,
            "next_week_issue": next_week_issue,
        }

    def test_existing_uuid_assignee_filter_still_works(self, issue_filter_data):
        result = ComplexFilterBackend().filter_queryset(
            _request_for(issue_filter_data["first_user"]),
            Issue.objects.all(),
            _IssueFilterView(),
            filter_data={"assignee_id__in": str(issue_filter_data["first_user"].id)},
        )

        assert list(result) == [issue_filter_data["first_issue"]]

    def test_existing_date_exact_and_range_filters_still_work(self, issue_filter_data):
        exact_result = ComplexFilterBackend().filter_queryset(
            _request_for(issue_filter_data["first_user"]),
            Issue.objects.all(),
            _IssueFilterView(),
            filter_data={"target_date__exact": "2026-05-31"},
        )
        range_result = ComplexFilterBackend().filter_queryset(
            _request_for(issue_filter_data["first_user"]),
            Issue.objects.all(),
            _IssueFilterView(),
            filter_data={"target_date__range": "2026-05-31,2026-06-01"},
        )

        assert list(exact_result) == [issue_filter_data["first_issue"]]
        assert set(range_result) == {issue_filter_data["first_issue"], issue_filter_data["second_issue"]}

    def test_current_user_filter_returns_results_for_the_request_user(self, issue_filter_data):
        payload = {"assignee_id__in": DYNAMIC_FILTER_TOKEN_CURRENT_USER}

        first_result = ComplexFilterBackend().filter_queryset(
            _request_for(issue_filter_data["first_user"]),
            Issue.objects.all(),
            _IssueFilterView(),
            filter_data=payload,
        )
        second_result = ComplexFilterBackend().filter_queryset(
            _request_for(issue_filter_data["second_user"]),
            Issue.objects.all(),
            _IssueFilterView(),
            filter_data=payload,
        )

        assert list(first_result) == [issue_filter_data["first_issue"]]
        assert list(second_result) == [issue_filter_data["second_issue"]]
        assert payload == {"assignee_id__in": DYNAMIC_FILTER_TOKEN_CURRENT_USER}

    def test_due_date_lte_end_of_week_includes_current_week_only(self, issue_filter_data, monkeypatch):
        user = issue_filter_data["first_user"]
        user.user_timezone = "UTC"
        _freeze_now(monkeypatch, datetime(2026, 5, 29, 20, 0, tzinfo=datetime_timezone.utc))

        result = ComplexFilterBackend().filter_queryset(
            _request_for(user),
            Issue.objects.all(),
            _IssueFilterView(),
            filter_data={"target_date__lte": DYNAMIC_FILTER_TOKEN_END_OF_WEEK},
        )

        assert set(result) == {issue_filter_data["first_issue"]}
        assert issue_filter_data["next_week_issue"] not in result

    def test_issue_filterset_declares_lte_for_date_fields(self):
        assert "target_date__lte" in IssueFilterSet.base_filters
        assert "start_date__lte" in IssueFilterSet.base_filters
        assert "created_at__lte" in IssueFilterSet.base_filters
        assert "updated_at__lte" in IssueFilterSet.base_filters
