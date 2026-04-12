# Plane Keycloak SSO Implementation Plan

Date: 12/04/26

## Scope

This plan covers the code and deploy work required to make `Keycloak` SSO work in this `Plane` fork.

## Phase 0: Deployment hygiene

Before changing auth code:

1. keep server deploys on `release/preprod`
2. keep server-only runtime changes in `docker-compose.override.yml`
3. avoid working directly on server branch `preview`

## Phase 1: Config surface

Add OIDC configuration keys to the instance-config system.

### Files

- `apps/api/plane/utils/instance_config_variables/core.py`
- `apps/api/plane/license/api/views/instance.py`
- `apps/api/plane/license/management/commands/configure_instance.py`

### Keys

- `IS_OIDC_ENABLED`
- `OIDC_PROVIDER_NAME`
- `OIDC_ISSUER`
- `OIDC_CLIENT_ID`
- `OIDC_CLIENT_SECRET`
- `OIDC_SCOPE`
- `OIDC_EMAIL_CLAIM`
- `OIDC_FIRST_NAME_CLAIM`
- `OIDC_LAST_NAME_CLAIM`
- `OIDC_UID_CLAIM`
- `OIDC_GROUPS_CLAIM`
- `OIDC_ACCESS_GROUP`
- `OIDC_ADMIN_GROUP`
- `OIDC_MEMBER_GROUP`
- `OIDC_GUEST_GROUP`
- `OIDC_DEFAULT_WORKSPACE_SLUG`

## Phase 2: Account model support

Add `oidc` to local account provider choices.

### Files

- `apps/api/plane/db/models/user.py`
- new migration in `apps/api/plane/db/migrations/`

### Requirement

Local account linking must use `sub` as `provider_account_id`.

## Phase 3: Generic OIDC provider

Implement a discovery-driven provider instead of hard-coding `Keycloak` endpoints.

### Files

- new: `apps/api/plane/authentication/provider/oauth/oidc.py`
- reference:
  - `apps/api/plane/authentication/provider/oauth/google.py`
  - `apps/api/plane/authentication/adapter/oauth.py`

### Responsibilities

- fetch discovery document
- build authorization URL
- exchange `code` for token
- fetch `userinfo`
- populate local `user_data`
- persist `Account`

## Phase 4: Callback routes

### Files

- `apps/api/plane/authentication/urls.py`
- `apps/api/plane/authentication/views/__init__.py`
- new: `apps/api/plane/authentication/views/app/oidc.py`
- new: `apps/api/plane/authentication/views/space/oidc.py`

### Routes

- `/auth/oidc/`
- `/auth/oidc/callback/`
- `/auth/spaces/oidc/`
- `/auth/spaces/oidc/callback/`

## Phase 5: Provisioning and role sync

### Requirements

- deny login without `/access/plane`
- link or create user
- create `WorkspaceMember` for workspace `kallistomed`
- update `WorkspaceMember.role` from group mapping
- set `Profile.last_workspace_id`

### Likely files

- OIDC provider
- callback views
- helper under `apps/api/plane/authentication/utils/`

## Phase 6: Web login UI

### Files

- `apps/web/core/hooks/oauth/core.tsx`
- any supporting type files touched by config changes

### Result

The main login screen should show an OIDC button when `is_oidc_enabled`.

## Phase 7: Admin UI

### Files

- `apps/admin/hooks/oauth/core.tsx`
- new: `apps/admin/components/authentication/oidc-config.tsx`
- new: `apps/admin/app/(all)/(dashboard)/authentication/oidc/page.tsx`
- new: `apps/admin/app/(all)/(dashboard)/authentication/oidc/form.tsx`

### Note

This is important, but it is not required for the first working SSO milestone if env-based config is already available.

## Phase 8: Logout

If discovery exposes `end_session_endpoint`, route logout through it after clearing the local session.

## Phase 9: Tests

Minimum test matrix:

1. success login
2. state mismatch
3. missing code
4. missing email
5. missing sub
6. no `/access/plane`
7. link existing user by `sub`
8. link existing user by exact email
9. create new user
10. create workspace membership
11. role -> `20`
12. role -> `15`
13. role -> `5`
14. repeated login is idempotent
