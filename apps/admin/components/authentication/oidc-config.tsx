/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { observer } from "mobx-react";
import Link from "next/link";
import { Settings2 } from "lucide-react";
import { getButtonStyling } from "@plane/propel/button";
import type { TInstanceAuthenticationMethodKeys } from "@plane/types";
import { ToggleSwitch } from "@plane/ui";
import { cn } from "@plane/utils";
import { isOIDCConfigured } from "@/components/authentication/oidc-config.helpers";
import { useInstance } from "@/hooks/store";

type Props = {
  disabled: boolean;
  updateConfig: (key: TInstanceAuthenticationMethodKeys, value: string) => void;
};

export const OIDCConfiguration = observer(function OIDCConfiguration(props: Props) {
  const { disabled, updateConfig } = props;
  const { formattedConfig } = useInstance();

  const enableOIDCConfig = formattedConfig?.IS_OIDC_ENABLED ?? "";
  const canToggleOIDC = isOIDCConfigured(formattedConfig) || Boolean(parseInt(enableOIDCConfig, 10));

  return (
    <>
      {isOIDCConfigured(formattedConfig) ? (
        <div className="flex items-center gap-4">
          <Link href="/authentication/oidc" className={cn(getButtonStyling("link", "base"), "font-medium")}>
            Edit
          </Link>
          <ToggleSwitch
            value={Boolean(parseInt(enableOIDCConfig, 10))}
            onChange={() => {
              const newEnableOIDCConfig = Boolean(parseInt(enableOIDCConfig, 10)) === true ? "0" : "1";
              updateConfig("IS_OIDC_ENABLED", newEnableOIDCConfig);
            }}
            size="sm"
            disabled={disabled || !canToggleOIDC}
          />
        </div>
      ) : (
        <Link href="/authentication/oidc" className={cn(getButtonStyling("secondary", "base"), "text-tertiary")}>
          <Settings2 className="h-4 w-4 p-0.5 text-tertiary" />
          Configure
        </Link>
      )}
    </>
  );
});
