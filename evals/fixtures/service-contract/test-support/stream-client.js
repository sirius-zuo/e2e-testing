/**
 * Stream client adapter for service contract fixture.
 * Uses Node.js built-in http module only.
 */

import { requestHttp } from "./http-client.js";

/**
 * Append an event to the stream.
 * @param {object} event - { correlationId, type, ... }
 * @returns {Promise<{appended: boolean, correlationId: string}>}
 */
export async function appendStream(event) {
  const { status, body } = await requestHttp({
    method: "POST",
    path: "/stream/append",
    body: event,
  });
  return { appended: status === 200, correlationId: body.correlationId || "" };
}

/**
 * Read an event from the stream.
 * @param {string} correlationId - The correlation ID to read
 * @param {object} options - { timeoutMs, commit }
 * @returns {Promise<{event: object, cursorCommitted: boolean, partition: number, offset: number}>}
 */
export async function readStream(correlationId, options = {}) {
  const { timeoutMs, commit = false } = options;
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
      path: "/stream/read",
      body: { correlationId, commit },
    });

    if (status === 200) {
      return {
        event: body.event,
        cursorCommitted: body.cursorCommitted,
        partition: body.partition,
        offset: body.offset,
      };
    }

    // Wait before retry
    await new Promise((resolve) => setTimeout(resolve, 50));
  }

  throw new Error(`bounded observation timed out for ${correlationId}`);
}

export default readStream;
