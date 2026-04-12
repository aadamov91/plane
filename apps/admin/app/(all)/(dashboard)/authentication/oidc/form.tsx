/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

import { useState } from "react";
import { isEmpty } from "lodash-es";
import Link from "next/link";
import { useForm } from "react-hook-form";
import { Monitor } from "lucide-react";
import { API_BASE_URL } from "@plane/constants";
import { Button, getButtonStyling } from "@plane/propel/button";
import { TOAST_TYPE, setToast } from "@plane/propel/toast";
import type { IFormattedInstanceConfiguration } from "@plane/types";
import { ToggleSwitch } from "@plane/ui";
import {
  buildOIDCConfigFormValues,
  buildOIDCConfigValuesFromResponse,
  type TOIDCConfigFormValues,
} from "@/components/authentication/oidc-config.helpers";
import { CodeBlock } from "@/components/common/code-block";
import { ConfirmDiscardModal } from "@/components/common/confirm-discard-modal";
import { ControllerInput } from "@/components/common/controller-input";
import type { TControllerInputFormField } from "@/components/common/controller-input";
import { CopyField } from "@/components/common/copy-field";
import type { TCopyField } from "@/components/common/copy-field";
import { useInstance } from "@/hooks/store";

type Props = {
  config: IFormattedInstanceConfiguration;
};

export function InstanceOIDCConfigForm(props: Props) {
  const { config } = props;
  const [isDiscardChangesModalOpen, setIsDiscardChangesModalOpen] = useState(false);
  const { updateInstanceConfigurations } = useInstance();
  const {
    handleSubmit,
    control,
    reset,
    watch,
    setValue,
    formState: { errors, isDirty, isSubmitting },
  } = useForm<TOIDCConfigFormValues>({
    defaultValues: buildOIDCConfigFormValues(config),
  });

  const originURL = !isEmpty(API_BASE_URL) ? API_BASE_URL : typeof window !== "undefined" ? window.location.origin : "";
  const providerName = watch("OIDC_PROVIDER_NAME")?.trim() || "OpenID Connect";
  const requireVerifiedEmail = watch("OIDC_REQUIRE_VERIFIED_EMAIL") === "1";

  const OIDC_CONNECTION_FIELDS: TControllerInputFormField[] = [
    {
      key: "OIDC_PROVIDER_NAME",
      type: "text",
      label: "Provider name",
      description: "This label is shown to users in the sign-in UI when OIDC is enabled.",
      placeholder: "Company SSO",
      error: Boolean(errors.OIDC_PROVIDER_NAME),
      required: true,
    },
    {
      key: "OIDC_ISSUER",
      type: "text",
      label: "Issuer URL",
      description: (
        <>
          Use the issuer root for your provider. Plane resolves the discovery document from this value, for example{" "}
          <CodeBlock darkerShade>https://id.example.com/realms/main</CodeBlock>.
        </>
      ),
      placeholder: "https://id.example.com/realms/main",
      error: Boolean(errors.OIDC_ISSUER),
      required: true,
    },
    {
      key: "OIDC_CLIENT_ID",
      type: "text",
      label: "Client ID",
      description: "Use the client identifier configured for the Plane application in your OIDC provider.",
      placeholder: "plane",
      error: Boolean(errors.OIDC_CLIENT_ID),
      required: true,
    },
    {
      key: "OIDC_CLIENT_SECRET",
      type: "password",
      label: "Client secret",
      description: "Use the client secret configured for the Plane application in your OIDC provider.",
      placeholder: "secret-value",
      error: Boolean(errors.OIDC_CLIENT_SECRET),
      required: true,
    },
    {
      key: "OIDC_SCOPE",
      type: "text",
      label: "Scopes",
      description: "Leave the default unless your OIDC provider requires additional scopes.",
      placeholder: "openid profile email",
      error: Boolean(errors.OIDC_SCOPE),
      required: true,
    },
  ];

  const OIDC_CLAIM_FIELDS: TControllerInputFormField[] = [
    {
      key: "OIDC_EMAIL_CLAIM",
      type: "text",
      label: "Email claim",
      description: "Claim name used for the user's email address.",
      placeholder: "email",
      error: Boolean(errors.OIDC_EMAIL_CLAIM),
      required: true,
    },
    {
      key: "OIDC_FIRST_NAME_CLAIM",
      type: "text",
      label: "First name claim",
      description: "Claim name used for the user's first name.",
      placeholder: "given_name",
      error: Boolean(errors.OIDC_FIRST_NAME_CLAIM),
      required: true,
    },
    {
      key: "OIDC_LAST_NAME_CLAIM",
      type: "text",
      label: "Last name claim",
      description: "Claim name used for the user's last name.",
      placeholder: "family_name",
      error: Boolean(errors.OIDC_LAST_NAME_CLAIM),
      required: true,
    },
    {
      key: "OIDC_UID_CLAIM",
      type: "text",
      label: "User ID claim",
      description: "Claim name used as the immutable external identity key.",
      placeholder: "sub",
      error: Boolean(errors.OIDC_UID_CLAIM),
      required: true,
    },
    {
      key: "OIDC_GROUPS_CLAIM",
      type: "text",
      label: "Groups claim",
      description: "Claim name used to evaluate access and workspace role mapping.",
      placeholder: "groups",
      error: Boolean(errors.OIDC_GROUPS_CLAIM),
      required: true,
    },
  ];

  const OIDC_ACCESS_FIELDS: TControllerInputFormField[] = [
    {
      key: "OIDC_ACCESS_GROUP",
      type: "text",
      label: "Access group",
      description: "Users must have this group in the OIDC groups claim to sign in to Plane.",
      placeholder: "/access/plane",
      error: Boolean(errors.OIDC_ACCESS_GROUP),
      required: true,
    },
    {
      key: "OIDC_ADMIN_GROUP",
      type: "text",
      label: "Admin role group",
      description: "Optional group that maps the user to the Plane Admin workspace role.",
      placeholder: "/plane/admin",
      error: Boolean(errors.OIDC_ADMIN_GROUP),
      required: false,
    },
    {
      key: "OIDC_MEMBER_GROUP",
      type: "text",
      label: "Member role group",
      description: "Optional group that maps the user to the Plane Member workspace role.",
      placeholder: "/plane/member",
      error: Boolean(errors.OIDC_MEMBER_GROUP),
      required: false,
    },
    {
      key: "OIDC_GUEST_GROUP",
      type: "text",
      label: "Guest role group",
      description: "Optional group that maps the user to the Plane Guest workspace role.",
      placeholder: "/plane/viewer",
      error: Boolean(errors.OIDC_GUEST_GROUP),
      required: false,
    },
    {
      key: "OIDC_DEFAULT_WORKSPACE_SLUG",
      type: "text",
      label: "Default workspace slug",
      description: "Optional workspace slug used for post-login provisioning and redirects.",
      placeholder: "main",
      error: Boolean(errors.OIDC_DEFAULT_WORKSPACE_SLUG),
      required: false,
    },
  ];

  const OIDC_SERVICE_DETAILS: TCopyField[] = [
    {
      key: "App_Callback_URI",
      label: "App callback URI",
      url: `${originURL}/auth/oidc/callback/`,
      description: <p>Register this redirect URI in your OIDC provider for the main Plane web application.</p>,
    },
    {
      key: "Mobile_Callback_URI",
      label: "Mobile callback URI",
      url: `${originURL}/auth/mobile/oidc/callback/`,
      description: (
        <p>Register this redirect URI in your OIDC provider if you want OIDC sign-in from Plane mobile clients.</p>
      ),
    },
    {
      key: "Space_Callback_URI",
      label: "Space callback URI",
      url: `${originURL}/auth/spaces/oidc/callback/`,
      description: (
        <p>
          Register this redirect URI in your OIDC provider if you want OIDC sign-in from the Plane Spaces experience.
        </p>
      ),
    },
  ];

  const onSubmit = async (formData: TOIDCConfigFormValues) => {
    const payload: Partial<TOIDCConfigFormValues> = { ...formData };

    try {
      const response = await updateInstanceConfigurations(payload);
      setToast({
        type: TOAST_TYPE.SUCCESS,
        title: "Done!",
        message: `${providerName} authentication is configured. Test sign-in before enabling it for all users.`,
      });
      reset(buildOIDCConfigValuesFromResponse(response));
    } catch {
      setToast({
        type: TOAST_TYPE.ERROR,
        title: "Unable to save changes",
        message: "Plane could not update the OIDC configuration. Review the values and try again.",
      });
    }
  };

  const handleGoBack = (e: React.MouseEvent<HTMLAnchorElement, MouseEvent>) => {
    if (isDirty) {
      e.preventDefault();
      setIsDiscardChangesModalOpen(true);
    }
  };

  return (
    <>
      <ConfirmDiscardModal
        isOpen={isDiscardChangesModalOpen}
        onDiscardHref="/authentication"
        handleClose={() => setIsDiscardChangesModalOpen(false)}
      />
      <div className="flex flex-col gap-8">
        <div className="grid w-full grid-cols-2 gap-x-12 gap-y-8">
          <div className="col-span-2 flex flex-col gap-y-6 pt-1 md:col-span-1">
            <div className="flex flex-col gap-y-2">
              <div className="pt-2.5 text-18 font-medium">{providerName}-provided details for Plane</div>
              <p className="text-11 text-tertiary">
                Complete the issuer, client credentials, and access group before enabling OIDC in authentication
                settings.
              </p>
            </div>

            <div className="flex flex-col gap-y-4">
              {OIDC_CONNECTION_FIELDS.map((field) => (
                <ControllerInput
                  key={field.key}
                  control={control}
                  type={field.type}
                  name={field.key}
                  label={field.label}
                  description={field.description}
                  placeholder={field.placeholder}
                  error={field.error}
                  required={field.required}
                />
              ))}
            </div>

            <div className="flex flex-col gap-y-4 pt-2">
              <div className="text-18 font-medium">Claims mapping</div>
              {OIDC_CLAIM_FIELDS.map((field) => (
                <ControllerInput
                  key={field.key}
                  control={control}
                  type={field.type}
                  name={field.key}
                  label={field.label}
                  description={field.description}
                  placeholder={field.placeholder}
                  error={field.error}
                  required={field.required}
                />
              ))}
              <div className="flex items-start justify-between gap-4 rounded-lg border border-subtle bg-layer-1 px-4 py-3">
                <div className="space-y-1">
                  <div className="text-13 font-medium text-primary">Require verified email</div>
                  <p className="text-11 text-tertiary">
                    Keep this enabled unless your OIDC provider cannot supply a trustworthy{" "}
                    <CodeBlock darkerShade>email_verified</CodeBlock> claim.
                  </p>
                </div>
                <ToggleSwitch
                  value={requireVerifiedEmail}
                  onChange={() =>
                    setValue("OIDC_REQUIRE_VERIFIED_EMAIL", requireVerifiedEmail ? "0" : "1", {
                      shouldDirty: true,
                    })
                  }
                  size="sm"
                />
              </div>
            </div>

            <div className="flex flex-col gap-y-4 pt-2">
              <div className="text-18 font-medium">Access and workspace mapping</div>
              {OIDC_ACCESS_FIELDS.map((field) => (
                <ControllerInput
                  key={field.key}
                  control={control}
                  type={field.type}
                  name={field.key}
                  label={field.label}
                  description={field.description}
                  placeholder={field.placeholder}
                  error={field.error}
                  required={field.required}
                />
              ))}
            </div>

            <div className="flex flex-col gap-1 pt-4">
              <div className="flex items-center gap-4">
                <Button
                  variant="primary"
                  size="lg"
                  onClick={(e) => void handleSubmit(onSubmit)(e)}
                  loading={isSubmitting}
                  disabled={!isDirty}
                >
                  {isSubmitting ? "Saving" : "Save changes"}
                </Button>
                <Link href="/authentication" className={getButtonStyling("secondary", "lg")} onClick={handleGoBack}>
                  Go back
                </Link>
              </div>
            </div>
          </div>

          <div className="col-span-2 flex flex-col gap-y-6 md:col-span-1">
            <div className="pt-2 text-18 font-medium">Plane-provided details for {providerName}</div>
            <div className="rounded-lg border border-subtle bg-layer-1 px-6 py-4 text-11 text-tertiary">
              Plane already enforces the backend OIDC security boundary. This page only manages the thin configuration
              layer and the redirect URIs your provider needs to trust.
            </div>
            <div className="flex flex-col overflow-hidden rounded-lg">
              <div className="flex items-center gap-x-3 bg-layer-3 px-6 py-3 text-11 font-medium text-secondary uppercase">
                <Monitor className="h-3 w-3" />
                Callback URIs
              </div>
              <div className="flex flex-col gap-y-4 bg-layer-1 px-6 py-4">
                {OIDC_SERVICE_DETAILS.map((field) => (
                  <CopyField key={field.key} label={field.label} url={field.url} description={field.description} />
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </>
  );
}
