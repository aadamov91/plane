/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import type { IInstanceConfiguration, TInstanceOIDCAuthenticationConfigurationKeys } from "@plane/types";

export type TOIDCConfigFormValues = Record<TInstanceOIDCAuthenticationConfigurationKeys, string>;

export const OIDC_REQUIRED_CONFIG_KEYS: TInstanceOIDCAuthenticationConfigurationKeys[] = [
  "OIDC_ISSUER",
  "OIDC_CLIENT_ID",
  "OIDC_CLIENT_SECRET",
  "OIDC_ACCESS_GROUP",
];

const OIDC_CONFIG_DEFAULTS: TOIDCConfigFormValues = {
  OIDC_PROVIDER_NAME: "OpenID Connect",
  OIDC_ISSUER: "",
  OIDC_CLIENT_ID: "",
  OIDC_CLIENT_SECRET: "",
  OIDC_SCOPE: "openid profile email",
  OIDC_EMAIL_CLAIM: "email",
  OIDC_FIRST_NAME_CLAIM: "given_name",
  OIDC_LAST_NAME_CLAIM: "family_name",
  OIDC_UID_CLAIM: "sub",
  OIDC_GROUPS_CLAIM: "groups",
  OIDC_REQUIRE_VERIFIED_EMAIL: "1",
  OIDC_ACCESS_GROUP: "",
  OIDC_ADMIN_GROUP: "",
  OIDC_MEMBER_GROUP: "",
  OIDC_GUEST_GROUP: "",
  OIDC_DEFAULT_WORKSPACE_SLUG: "",
};

const OIDC_CONFIG_KEY_SET = new Set<string>(Object.keys(OIDC_CONFIG_DEFAULTS));

type TOIDCConfigLike = Partial<Record<TInstanceOIDCAuthenticationConfigurationKeys, string>>;

export const isOIDCConfigured = (config?: TOIDCConfigLike): boolean =>
  OIDC_REQUIRED_CONFIG_KEYS.every((key) => Boolean(config?.[key]?.trim()));

export const buildOIDCConfigFormValues = (config?: TOIDCConfigLike): TOIDCConfigFormValues => ({
  OIDC_PROVIDER_NAME: config?.OIDC_PROVIDER_NAME || OIDC_CONFIG_DEFAULTS.OIDC_PROVIDER_NAME,
  OIDC_ISSUER: config?.OIDC_ISSUER || OIDC_CONFIG_DEFAULTS.OIDC_ISSUER,
  OIDC_CLIENT_ID: config?.OIDC_CLIENT_ID || OIDC_CONFIG_DEFAULTS.OIDC_CLIENT_ID,
  OIDC_CLIENT_SECRET: config?.OIDC_CLIENT_SECRET || OIDC_CONFIG_DEFAULTS.OIDC_CLIENT_SECRET,
  OIDC_SCOPE: config?.OIDC_SCOPE || OIDC_CONFIG_DEFAULTS.OIDC_SCOPE,
  OIDC_EMAIL_CLAIM: config?.OIDC_EMAIL_CLAIM || OIDC_CONFIG_DEFAULTS.OIDC_EMAIL_CLAIM,
  OIDC_FIRST_NAME_CLAIM: config?.OIDC_FIRST_NAME_CLAIM || OIDC_CONFIG_DEFAULTS.OIDC_FIRST_NAME_CLAIM,
  OIDC_LAST_NAME_CLAIM: config?.OIDC_LAST_NAME_CLAIM || OIDC_CONFIG_DEFAULTS.OIDC_LAST_NAME_CLAIM,
  OIDC_UID_CLAIM: config?.OIDC_UID_CLAIM || OIDC_CONFIG_DEFAULTS.OIDC_UID_CLAIM,
  OIDC_GROUPS_CLAIM: config?.OIDC_GROUPS_CLAIM || OIDC_CONFIG_DEFAULTS.OIDC_GROUPS_CLAIM,
  OIDC_REQUIRE_VERIFIED_EMAIL: config?.OIDC_REQUIRE_VERIFIED_EMAIL || OIDC_CONFIG_DEFAULTS.OIDC_REQUIRE_VERIFIED_EMAIL,
  OIDC_ACCESS_GROUP: config?.OIDC_ACCESS_GROUP || OIDC_CONFIG_DEFAULTS.OIDC_ACCESS_GROUP,
  OIDC_ADMIN_GROUP: config?.OIDC_ADMIN_GROUP || OIDC_CONFIG_DEFAULTS.OIDC_ADMIN_GROUP,
  OIDC_MEMBER_GROUP: config?.OIDC_MEMBER_GROUP || OIDC_CONFIG_DEFAULTS.OIDC_MEMBER_GROUP,
  OIDC_GUEST_GROUP: config?.OIDC_GUEST_GROUP || OIDC_CONFIG_DEFAULTS.OIDC_GUEST_GROUP,
  OIDC_DEFAULT_WORKSPACE_SLUG: config?.OIDC_DEFAULT_WORKSPACE_SLUG || OIDC_CONFIG_DEFAULTS.OIDC_DEFAULT_WORKSPACE_SLUG,
});

export const buildOIDCConfigValuesFromResponse = (
  response: Pick<IInstanceConfiguration, "key" | "value">[]
): TOIDCConfigFormValues => {
  const oidcConfig = response.reduce<Partial<TOIDCConfigFormValues>>((accumulator, item) => {
    if (!OIDC_CONFIG_KEY_SET.has(item.key)) return accumulator;

    accumulator[item.key as TInstanceOIDCAuthenticationConfigurationKeys] = item.value;
    return accumulator;
  }, {});

  return buildOIDCConfigFormValues(oidcConfig);
};
