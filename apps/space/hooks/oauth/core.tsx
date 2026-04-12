/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

// plane imports
import { useSearchParams } from "next/navigation";
import { useTheme } from "next-themes";
import { KeyRound } from "lucide-react";
import { API_BASE_URL } from "@plane/constants";
import { useTranslation } from "@plane/i18n";
import type { TOAuthConfigs, TOAuthOption } from "@plane/types";
// assets
import giteaLogo from "@/app/assets/logos/gitea-logo.svg?url";
import githubLightLogo from "@/app/assets/logos/github-black.png?url";
import githubDarkLogo from "@/app/assets/logos/github-dark.svg?url";
import gitlabLogo from "@/app/assets/logos/gitlab-logo.svg?url";
import googleLogo from "@/app/assets/logos/google-logo.svg?url";
// hooks
import { useInstance } from "@/hooks/store/use-instance";

export const useCoreOAuthConfig = (oauthActionText: string): TOAuthConfigs => {
  //router
  const searchParams = useSearchParams();
  // query params
  const next_path = searchParams.get("next_path");
  // theme
  const { resolvedTheme } = useTheme();
  const { t } = useTranslation();
  // store hooks
  const { config } = useInstance();
  const getOAuthRoute = (route: string) => `${API_BASE_URL}${route}${next_path ? `?next_path=${next_path}` : ``}`;
  const oidcProviderName = config?.oidc_provider_name?.trim() || "OpenID Connect";
  const getOAuthButtonText = (providerName: string) => {
    if (oauthActionText === "Sign up") return t("auth.ui.oauth.sign_up_with_provider", { provider: providerName });
    if (oauthActionText === "Sign in") return t("auth.ui.oauth.sign_in_with_provider", { provider: providerName });
    return t("auth.ui.oauth.continue_with_provider", { provider: providerName });
  };
  // derived values
  const isOAuthEnabled =
    (config &&
      (config?.is_google_enabled ||
        config?.is_github_enabled ||
        config?.is_gitlab_enabled ||
        config?.is_gitea_enabled ||
        config?.is_oidc_enabled)) ||
    false;
  const oAuthOptions: TOAuthOption[] = [
    {
      id: "google",
      text: getOAuthButtonText("Google"),
      icon: <img src={googleLogo} height={18} width={18} alt="Google Logo" />,
      onClick: () => {
        window.location.assign(getOAuthRoute("/auth/google/"));
      },
      enabled: config?.is_google_enabled,
    },
    {
      id: "github",
      text: getOAuthButtonText("GitHub"),
      icon: (
        <img
          src={resolvedTheme === "dark" ? githubLightLogo : githubDarkLogo}
          height={18}
          width={18}
          alt="GitHub Logo"
        />
      ),
      onClick: () => {
        window.location.assign(getOAuthRoute("/auth/github/"));
      },
      enabled: config?.is_github_enabled,
    },
    {
      id: "gitlab",
      text: getOAuthButtonText("GitLab"),
      icon: <img src={gitlabLogo} height={18} width={18} alt="GitLab Logo" />,
      onClick: () => {
        window.location.assign(getOAuthRoute("/auth/gitlab/"));
      },
      enabled: config?.is_gitlab_enabled,
    },
    {
      id: "gitea",
      text: getOAuthButtonText("Gitea"),
      icon: <img src={giteaLogo} height={18} width={18} alt="Gitea Logo" />,
      onClick: () => {
        window.location.assign(getOAuthRoute("/auth/gitea/"));
      },
      enabled: config?.is_gitea_enabled,
    },
    {
      id: "oidc",
      text: getOAuthButtonText(oidcProviderName),
      icon: <KeyRound className="h-[18px] w-[18px] text-tertiary" />,
      onClick: () => {
        window.location.assign(getOAuthRoute("/auth/spaces/oidc/"));
      },
      enabled: config?.is_oidc_enabled,
    },
  ];

  return {
    isOAuthEnabled,
    oAuthOptions,
  };
};
