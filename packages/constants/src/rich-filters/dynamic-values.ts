/**
 * Copyright (c) 2023-present Plane Software, Inc. and contributors
 * SPDX-License-Identifier: AGPL-3.0-only
 * See the LICENSE file for details.
 */

export const RICH_FILTER_DYNAMIC_VALUE = {
  CURRENT_USER: "current_user",
  TODAY: "today",
  END_OF_WEEK: "end_of_week",
} as const;

export type TRichFilterDynamicValue =
  (typeof RICH_FILTER_DYNAMIC_VALUE)[keyof typeof RICH_FILTER_DYNAMIC_VALUE];

export type TRichFilterDynamicDateValue =
  | typeof RICH_FILTER_DYNAMIC_VALUE.TODAY
  | typeof RICH_FILTER_DYNAMIC_VALUE.END_OF_WEEK;

export const RICH_FILTER_DYNAMIC_VALUE_LABELS: Record<TRichFilterDynamicValue, string> = {
  [RICH_FILTER_DYNAMIC_VALUE.CURRENT_USER]: "Me",
  [RICH_FILTER_DYNAMIC_VALUE.TODAY]: "Today",
  [RICH_FILTER_DYNAMIC_VALUE.END_OF_WEEK]: "End of week",
} as const;

export const RICH_FILTER_DYNAMIC_DATE_OPTIONS: {
  id: TRichFilterDynamicDateValue;
  label: string;
  value: TRichFilterDynamicDateValue;
}[] = [
  {
    id: RICH_FILTER_DYNAMIC_VALUE.TODAY,
    label: RICH_FILTER_DYNAMIC_VALUE_LABELS[RICH_FILTER_DYNAMIC_VALUE.TODAY],
    value: RICH_FILTER_DYNAMIC_VALUE.TODAY,
  },
  {
    id: RICH_FILTER_DYNAMIC_VALUE.END_OF_WEEK,
    label: RICH_FILTER_DYNAMIC_VALUE_LABELS[RICH_FILTER_DYNAMIC_VALUE.END_OF_WEEK],
    value: RICH_FILTER_DYNAMIC_VALUE.END_OF_WEEK,
  },
];

export const isRichFilterDynamicDateValue = (value: unknown): value is TRichFilterDynamicDateValue =>
  value === RICH_FILTER_DYNAMIC_VALUE.TODAY || value === RICH_FILTER_DYNAMIC_VALUE.END_OF_WEEK;
