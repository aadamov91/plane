# Plane Keycloak SSO Docs

Date: 12/04/26

## Scope

These documents cover the `Keycloak` / `OIDC` implementation that belongs inside the `Plane` fork.

They are the local source of truth for:

- provider design
- callback routes
- `Account` linking
- workspace auto-provisioning
- `Keycloak` group to workspace-role mapping
- deploy policy for the fork

## Read in this order

1. [`plane_keycloak_sso_overview.md`](/home/alexa/plane-oidc-keycloak/docs/auth/plane_keycloak_sso_overview.md)
2. [`plane_keycloak_sso_implementation_plan.md`](/home/alexa/plane-oidc-keycloak/docs/auth/plane_keycloak_sso_implementation_plan.md)
3. [`plane_keycloak_sso_issue_backlog.md`](/home/alexa/plane-oidc-keycloak/docs/auth/plane_keycloak_sso_issue_backlog.md)
4. [`plane_keycloak_sso_deploy_runbook.md`](/home/alexa/plane-oidc-keycloak/docs/auth/plane_keycloak_sso_deploy_runbook.md)

## Important policy

- Implement `generic OIDC`, not a hard-coded `Keycloak-only` provider.
- Treat `Keycloak` as the identity owner.
- Treat `Plane` as the owner of:
  - local sessions
  - workspace membership
  - workspace role
  - app-specific permissions
- The first working milestone is:
  - login through `Keycloak`
  - local user provisioning
  - auto-add to workspace `kallistomed`
  - role mapping from `Keycloak` groups

## Branch policy

- `preview` = upstream mirror
- `develop` = integration branch
- `feature/oidc-keycloak` = active feature branch
- `release/preprod` = only branch deployed to the server
