# Plane Keycloak SSO Issue Backlog

Date: 12/04/26

## `PLANE-SSO-00` Move deployment to stable branch

### Goal

Stop deploying from `preview`.

### Done when

- server checkout is on `release/preprod`
- runtime overrides stay outside tracked source changes where possible

## `PLANE-SSO-01` Add OIDC config surface

### Goal

Expose all OIDC config values through instance configuration.

### Files

- `apps/api/plane/utils/instance_config_variables/core.py`
- `apps/api/plane/license/api/views/instance.py`
- `apps/api/plane/license/management/commands/configure_instance.py`

### Done when

- config API returns `is_oidc_enabled`
- OIDC values can be saved and reloaded

## `PLANE-SSO-02` Add `oidc` provider to `Account`

### Goal

Persist OIDC user links locally.

### Files

- `apps/api/plane/db/models/user.py`
- migration file

### Done when

- `Account(provider='oidc', provider_account_id=sub)` is valid

## `PLANE-SSO-03` Implement generic OIDC provider

### Goal

Build a provider that reads discovery from the issuer.

### Files

- `apps/api/plane/authentication/provider/oauth/oidc.py`

### Done when

- auth URL is generated
- token exchange works
- userinfo is parsed

## `PLANE-SSO-04` Add OIDC initiate and callback endpoints

### Files

- `apps/api/plane/authentication/urls.py`
- `apps/api/plane/authentication/views/__init__.py`
- `apps/api/plane/authentication/views/app/oidc.py`
- `apps/api/plane/authentication/views/space/oidc.py`

### Done when

- web login can start OIDC flow
- callback returns cleanly

## `PLANE-SSO-05` Link or create local users

### Goal

Handle both existing users and first-login provisioning.

### Done when

- user is matched by `sub`
- fallback exact-email linking works
- new user is created when needed

## `PLANE-SSO-06` Enforce `/access/plane`

### Goal

Prevent unauthorized realm users from entering Plane.

### Done when

- users without `/access/plane` are denied
- denial is a controlled auth failure, not a 500

## `PLANE-SSO-07` Auto-add user to workspace `kallistomed`

### Goal

Make SSO land users in the real workspace.

### Done when

- `WorkspaceMember` is created or updated
- `Profile.last_workspace_id` is set
- user lands in `kallistomed`

## `PLANE-SSO-08` Map groups to workspace role

### Goal

Use `Keycloak` groups to set role.

### Mapping

- `/plane/admin` -> `20`
- `/plane/member` -> `15`
- `/plane/viewer` -> `5`

### Done when

- role is correct on first login
- role updates on repeat login if group changes

## `PLANE-SSO-09` Add OIDC button to web auth screen

### Files

- `apps/web/core/hooks/oauth/core.tsx`

### Done when

- button appears when enabled
- button starts OIDC flow

## `PLANE-SSO-10` Add `/god-mode` OIDC settings UI

### Files

- `apps/admin/hooks/oauth/core.tsx`
- `apps/admin/components/authentication/oidc-config.tsx`
- `apps/admin/app/(all)/(dashboard)/authentication/oidc/page.tsx`
- `apps/admin/app/(all)/(dashboard)/authentication/oidc/form.tsx`

### Done when

- admins can configure OIDC without editing env manually

## `PLANE-SSO-11` Add logout support

### Goal

Support IdP logout where available.

### Done when

- local logout works
- IdP logout is used if supported by discovery

## `PLANE-SSO-12` Add support-grade error handling

### Goal

Make failures diagnosable without leaking secrets.

### Done when

- logs are useful
- secrets are not logged
- common failures return stable error codes

## `PLANE-SSO-13` Add backend tests

### Done when

- success, reject, invalid, duplicate, and idempotent flows are covered

## `PLANE-SSO-14` Deploy to preprod

### Done when

- branch `release/preprod` is deployed
- test user can login through Keycloak
- user lands in workspace `kallistomed`

## `PLANE-SSO-15` Post-cutover auth policy

### Goal

Document the final login policy.

### Done when

- break-glass admin path is defined
- onboarding steps for new users are documented
