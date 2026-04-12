# Plane Keycloak SSO Deploy Runbook

Date: 12/04/26

## Scope

Use this runbook when the forked `Plane` SSO implementation is ready to deploy.

## Server paths

- live checkout: `/opt/plane/repo`
- active deploy branch: `release/preprod`

## Keycloak setup

### Realm

- `kallistomed`

### Client

- `plane`

### Redirect URIs

- `https://plane.kallistomed.ru/auth/oidc/callback/`
- `https://plane.kallistomed.ru/auth/spaces/oidc/callback/`

### Required claims

- `sub`
- `email`
- `given_name`
- `family_name`
- `groups`

### Required groups

- `/access/plane`
- `/plane/admin`
- `/plane/member`
- `/plane/viewer`

## Expected runtime config

Recommended values:

- `OIDC_PROVIDER_NAME=Keycloak`
- `OIDC_ISSUER=https://auth.kallistomed.ru/realms/kallistomed`
- `OIDC_CLIENT_ID=plane`
- `OIDC_SCOPE=openid profile email`
- `OIDC_EMAIL_CLAIM=email`
- `OIDC_FIRST_NAME_CLAIM=given_name`
- `OIDC_LAST_NAME_CLAIM=family_name`
- `OIDC_UID_CLAIM=sub`
- `OIDC_GROUPS_CLAIM=groups`
- `OIDC_ACCESS_GROUP=/access/plane`
- `OIDC_ADMIN_GROUP=/plane/admin`
- `OIDC_MEMBER_GROUP=/plane/member`
- `OIDC_GUEST_GROUP=/plane/viewer`
- `OIDC_DEFAULT_WORKSPACE_SLUG=kallistomed`

## Deploy steps

1. push `release/preprod` to `origin`
2. on server:

```bash
cd /opt/plane/repo
git fetch origin
git checkout release/preprod
git pull --ff-only origin release/preprod
docker compose up -d migrator
docker compose up -d --build api worker beat-worker web admin space live
```

## Verification

### Runtime

```bash
cd /opt/plane/repo
docker compose ps
curl -I https://plane.kallistomed.ru
curl -I https://plane.kallistomed.ru/god-mode/
curl -I https://plane.kallistomed.ru/spaces/
```

### Auth flow

1. open `https://plane.kallistomed.ru`
2. click OIDC / Keycloak button
3. sign in with a realm user that has `/access/plane`
4. confirm user lands in workspace `kallistomed`

### Membership and role

Verify:

- local `Account` created with:
  - `provider = oidc`
  - `provider_account_id = sub`
- `WorkspaceMember` exists for `kallistomed`
- role matches group mapping

## Rollback

If the new release is broken:

```bash
cd /opt/plane/repo
git log --oneline -n 5
git checkout <previous-good-commit-or-branch>
docker compose up -d --build api worker beat-worker web admin space live
```

Keep at least one local break-glass admin path until OIDC is proven stable.
