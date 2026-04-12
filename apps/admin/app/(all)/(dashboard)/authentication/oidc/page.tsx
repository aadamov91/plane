/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { observer } from "mobx-react";
import useSWR from "swr";
import { KeyRound } from "lucide-react";
import { setPromiseToast } from "@plane/propel/toast";
import { Loader, ToggleSwitch } from "@plane/ui";
import { AuthenticationMethodCard } from "@/components/authentication/authentication-method-card";
import { canToggleOIDC, getOIDCProviderName, isOIDCEnabled } from "@/components/authentication/oidc-config.helpers";
import { PageWrapper } from "@/components/common/page-wrapper";
import { useInstance } from "@/hooks/store";
import type { Route } from "./+types/page";
import { InstanceOIDCConfigForm } from "./form";

const InstanceOIDCAuthenticationPage = observer(function InstanceOIDCAuthenticationPage(_props: Route.ComponentProps) {
  const { fetchInstanceConfigurations, formattedConfig, updateInstanceConfigurations } = useInstance();
  const [isSubmitting, setIsSubmitting] = useState<boolean>(false);
  const providerName = getOIDCProviderName(formattedConfig);

  useSWR("INSTANCE_CONFIGURATIONS", () => fetchInstanceConfigurations());

  const updateConfig = async (key: "IS_OIDC_ENABLED", value: string) => {
    setIsSubmitting(true);

    const payload = {
      [key]: value,
    };

    const updateConfigPromise = updateInstanceConfigurations(payload);

    setPromiseToast(updateConfigPromise, {
      loading: "Saving Configuration",
      success: {
        title: "Configuration saved",
        message: () => `${providerName} authentication is now ${value === "1" ? "active" : "disabled"}.`,
      },
      error: {
        title: "Error",
        message: () => "Failed to save configuration",
      },
    });

    try {
      await updateConfigPromise;
    } catch {
      // The promise toast already surfaces a safe error message.
    } finally {
      setIsSubmitting(false);
    }
  };

  const oidcEnabled = isOIDCEnabled(formattedConfig);
  const oidcToggleAllowed = canToggleOIDC(formattedConfig);

  return (
    <PageWrapper
      customHeader={
        <AuthenticationMethodCard
          name="OpenID Connect"
          description={`Allow members to login or sign up to Plane with your configured ${providerName} identity provider.`}
          icon={<KeyRound className="h-6 w-6 p-0.5 text-tertiary" />}
          config={
            <ToggleSwitch
              value={oidcEnabled}
              onChange={() => {
                updateConfig("IS_OIDC_ENABLED", oidcEnabled ? "0" : "1");
              }}
              size="sm"
              disabled={isSubmitting || !formattedConfig || !oidcToggleAllowed}
            />
          }
          disabled={isSubmitting || !formattedConfig}
          withBorder={false}
        />
      }
    >
      {formattedConfig ? (
        <InstanceOIDCConfigForm config={formattedConfig} />
      ) : (
        <Loader className="space-y-8">
          <Loader.Item height="50px" width="25%" />
          <Loader.Item height="50px" />
          <Loader.Item height="50px" />
          <Loader.Item height="50px" />
          <Loader.Item height="50px" width="50%" />
        </Loader>
      )}
    </PageWrapper>
  );
});

export const meta: Route.MetaFunction = () => [{ title: "OpenID Connect Authentication - God Mode" }];

export default InstanceOIDCAuthenticationPage;
