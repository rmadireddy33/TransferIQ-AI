import { descriptor, triggerDescriptor, type ConnectorValue } from "@uipath/maestro-builder-sdk";

export interface Event {
  /** The Event body */
  request_body?: string;
  /** The Event headers */
  request_headers?: string;
}

export interface HttpWebhookOutputs {
  /** Request body of the event sent to webhook endpoint */
  request_body?: string;
  /** Request headers of the event sent to webhook endpoint */
  request_headers?: string;
}

/**
 * HTTP Webhook — uipath.connector.event.uipath-http-webhook.http-webhook
 *
 * Start a flow on it with `onEvent(HttpWebhook, { where: { … } })`, or pause for it
 * with `waitForEvent(HttpWebhook, { … })`; `where` carries its event parameters.
 */
export const HttpWebhook = triggerDescriptor<Record<string, string>, HttpWebhookOutputs>()({
  connector: "uipath-http-webhook",
  event: "http-webhook",
  version: "1.0.0",
  displayName: "HTTP Webhook",
} as const);

export interface HttpWebhook_Outputs {
  /** Request body of the event sent to webhook endpoint */
  request_body?: string;
  /** Request headers of the event sent to webhook endpoint */
  request_headers?: string;
}

/**
 * HTTP Webhook — uipath.connector.trigger.uipath-http-webhook.http-webhook
 *
 * Start a flow on it with `onEvent(HttpWebhook_, { where: { … } })`, or pause for it
 * with `waitForEvent(HttpWebhook_, { … })`; `where` carries its event parameters.
 */
export const HttpWebhook_ = triggerDescriptor<Record<string, string>, HttpWebhook_Outputs>()({
  connector: "uipath-http-webhook",
  event: "http-webhook",
  version: "1.0.0",
  displayName: "HTTP Webhook",
} as const);

export interface GetTriggerEventOutputInputs {
  /** Use UiPathEventObjectId as the input argument to retrieve data. */
  "event-id": ConnectorValue<string>;
}

export interface GetTriggerEventOutputOutputs {
  Event?: Event;
}

/** Get Trigger Event Output — uipath.connector.uipath-http-webhook.get-trigger-event-output */
export const GetTriggerEventOutput = descriptor<GetTriggerEventOutputInputs, GetTriggerEventOutputOutputs>()({
  nodeType: "uipath.connector.uipath-http-webhook.get-trigger-event-output",
  version: "1.0.0",
  requiresConnection: true,
  requiresFolderKey: true,
} as const);
