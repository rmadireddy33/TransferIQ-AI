import { triggerDescriptor } from "@uipath/maestro-builder-sdk";

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
 *
 * After deploying, register the trigger's webhook URL in the connector app's
 * event-subscription settings; `registry prepare` prints the instructions.
 */
export const HttpWebhook = triggerDescriptor<Record<string, string>, HttpWebhookOutputs>()({
  connector: "uipath-http-webhook",
  event: "http-webhook",
  version: "1.0.0",
  displayName: "HTTP Webhook",
} as const);
