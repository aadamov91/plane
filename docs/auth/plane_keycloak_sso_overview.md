# Plane Keycloak SSO Overview

Date: 12/04/26

## Goal

Add `Keycloak` SSO to this `Plane` fork without depending on `Plane Pro / Business` features.

The target user experience is:

1. user clicks `Continue with Keycloak`
2. `Plane` redirects to `Keycloak`
3. `Keycloak` returns to the `Plane` callback
4. `Plane` links or creates a local user
5. `Plane` auto-adds the user to workspace `kallistomed`
6. `Plane` assigns workspace role from `Keycloak` groups
7. user lands inside the existing workspace instead of `create-workspace`

## Why this lives in the fork

Upstream `Plane CE` already has provider-specific OAuth patterns in code, but generic `OIDC SSO` is documented under paid editions.

Because of that, this implementation belongs in the fork:

- backend auth provider
- callback views
- config surface
- login UI
- admin UI
- tests

## Current live assumptions

- Plane host: `https://plane.kallistomed.ru`
- Keycloak issuer: `https://auth.kallistomed.ru/realms/kallistomed`
- Existing workspace:
  - name: `Kallistomed`
  - slug: `kallistomed`

## Identity model

`Keycloak` owns:

- `sub`
- `email`
- `given_name`
- `family_name`
- `groups`

`Plane` owns:

- local user record
- local session
- workspace membership
- workspace role

## Linking model

Use this order on callback:

1. find local account by:
   - `provider = oidc`
   - `provider_account_id = sub`
2. if not found, try exact email match
3. if exact email match exists, link that user to the OIDC account
4. if neither exists, create a new user

## Group mapping

Access gate:

- `/access/plane`

Workspace role mapping:

- `/plane/admin` -> `20` (`Admin`)
- `/plane/member` -> `15` (`Member`)
- `/plane/viewer` -> `5` (`Guest`)
- `/access/plane` only -> default `15`

## First milestone

Do not wait for polished admin UI before proving the feature.

The first valid milestone is:

- provider works through discovery
- callback succeeds
- local account is linked or created
- `WorkspaceMember` exists for `kallistomed`
- user lands inside the workspace
