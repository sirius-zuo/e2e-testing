/**
 * Queue client adapter for service contract fixture.
 * Uses Node.js built-in http module only.
 */

import { requestHttp } from "./http-client.js";

/**
 * Publish a message to the queue.
 * @param {object} message - { correlationId, type, ... }
 * @returns {Promise<{delivered: boolean, correlationId: string}>}
 */
export async function publishQueue(message) {
  const { status, body } = await requestHttp({
    method: "POST",
    path: "/queue/publish",
    body: message,
  });
  return { delivered: status === 200, correlationId: body.correlationId || "" };
}

/**
 * Consume a message from the queue.
 * @param {string} correlationId - The correlation ID to consume
 * @param {object} options - { timeoutMs, acknowledge }
 * @returns {Promise<{message: object, acknowledged: boolean, redeliveryCount: number}>}
 */
export async function consumeQueue(correlationId, options = {}) {
  const { timeoutMs, acknowledge = false } = options;
  if (!correlationId) {
    throw new Error("correlationId is required");
  }
  if (typeof timeoutMs !== "number" || timeoutMs <= 0) {
    throw new Error("timeoutMs must be a positive number");
  }
  if (timeoutMs > 5000) {
    throw new Error("timeoutMs must be bounded at 5000ms");
  }

  const deadline = Date.now() + timeoutMs;
  const maxAttempts = Math.floor(timeoutMs / 50);

  for (let attempt = 0; attempt < maxAttempts; attempt++) {
    if (Date.now() >= deadline) {
      throw new Error(`bounded observation timed out for ${correlationId}`);
    }

    const { status, body } = await requestHttp({
      method: "POST",
      path: "/queue/consume",
      body: { correlationId, acknowledge },
    });

    if (status === 200) {
      return {
        message: body.message,
        acknowledged: body.acknowledged,
        redeliveryCount: body.redeliveryCount,
      };
    }

    // Wait before retry
    await new Promise((resolve) => setTimeout(resolve, 50));
  }

  throw new Error(`bounded observation timed out for ${correlationId}`);
}

export default consumeQueue;
