/**
 * WebSocket client adapter for service contract fixture.
 * Uses Node.js built-in http module for handshake only.
 */

import http from "node:http";
import { createHash } from "node:crypto";

const BASE_URL = "http://127.0.0.1:43170";

/**
 * Exchange WebSocket messages with the fixture server.
 * @param {Array} sequence - Array of {type, ...} messages to send
 * @param {object} options - { timeoutMs }
 * @returns {Promise<{messages: Array, status: number}>}
 */
export async function exchangeWebSocket(sequence, options = {}) {
  const timeoutMs = options.timeoutMs || 5000;

  return new Promise((resolve, reject) => {
    const key = Buffer.from(Math.random().toString(36)).toString("base64").slice(0, 24);

    const req = http.request({
      hostname: "127.0.0.1",
      port: 43170,
      path: "/?ws=true",
      headers: {
        "Upgrade": "websocket",
        "Connection": "Upgrade",
        "Sec-WebSocket-Key": key,
        "Sec-WebSocket-Version": "13",
        "Sec-WebSocket-Protocol": "e2e-v1",
      },
      timeout: timeoutMs,
    }, (res) => {
      if (res.statusCode !== 101) {
        resolve({ messages: [], status: res.statusCode });
        return;
      }

      const accept = createHash("sha1")
        .update(key + "258EAFA5-E914-47DA-95CA-5AB9D8B23D4E")
        .digest("base64");

      if (res.headers["sec-websocket-accept"] !== accept) {
        resolve({ messages: [], status: 400 });
        return;
      }

      const messages = [];
      let timeoutId;

      const onMessage = (data) => {
        try {
          const msg = JSON.parse(data.toString());
          messages.push(msg);
        } catch {
          // Ignore non-JSON messages
        }
      };

      // Send sequence messages
      for (const msg of sequence) {
        const frame = createFrame(msg);
        req.write(frame);
      }

      // Read response messages with timeout
      timeoutId = setTimeout(() => {
        resolve({ messages, status: 200 });
      }, timeoutMs);

      res.on("data", onMessage);
      res.on("end", () => {
        clearTimeout(timeoutId);
        resolve({ messages, status: 200 });
      });
    });

    req.on("error", (err) => {
      resolve({ messages: [], status: 0, error: err.message });
    });

    req.on("timeout", () => {
      clearTimeout(timeoutId);
      req.destroy();
      resolve({ messages: [], status: 0 });
    });

    req.end();
  });
}

function createFrame(message) {
  const payload = JSON.stringify(message);
  // Simple frame format for fixture: length + payload
  return Buffer.from(`${payload.length}\n${payload}`);
}

export default exchangeWebSocket;
