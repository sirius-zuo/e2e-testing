/**
 * WebSocket client adapter for service contract fixture.
 * Performs a real RFC 6455 handshake and frame exchange over Node's http module.
 */

import http from "node:http";
import { createHash, randomBytes } from "node:crypto";
import { encodeFrame, decodeFrames } from "../src/ws-frames.js";

const HOST = "127.0.0.1";
const PORT = 43170;

/**
 * Exchange WebSocket messages with the fixture server.
 * @param {Array<object>} sequence - Messages to send after the handshake completes.
 * @param {object} options - { timeoutMs }
 * @returns {Promise<{messages: Array<object>, status: number}>}
 */
export async function exchangeWebSocket(sequence, options = {}) {
  const timeoutMs = options.timeoutMs || 5000;
  const key = randomBytes(16).toString("base64");

  return new Promise((resolve) => {
    const messages = [];
    let settled = false;

    const finish = (result) => {
      if (settled) return;
      settled = true;
      clearTimeout(timer);
      resolve(result);
    };

    const req = http.request({
      hostname: HOST,
      port: PORT,
      path: "/?ws=true",
      headers: {
        "Upgrade": "websocket",
        "Connection": "Upgrade",
        "Sec-WebSocket-Key": key,
        "Sec-WebSocket-Version": "13",
        "Sec-WebSocket-Protocol": "e2e-v1",
      },
    });

    const timer = setTimeout(() => {
      req.destroy();
      finish({ messages, status: 200 });
    }, timeoutMs);

    req.on("upgrade", (res, socket, head) => {
      if (res.statusCode !== 101) {
        finish({ messages: [], status: res.statusCode });
        return;
      }
      const expectedAccept = createHash("sha1")
        .update(key + "258EAFA5-E914-47DA-95CA-5AB9D8B23D4E")
        .digest("base64");
      if (res.headers["sec-websocket-accept"] !== expectedAccept) {
        finish({ messages: [], status: 400 });
        return;
      }

      let buffer = head && head.length ? Buffer.from(head) : Buffer.alloc(0);
      socket.on("data", (chunk) => {
        buffer = Buffer.concat([buffer, chunk]);
        const { messages: decoded, remainder } = decodeFrames(buffer);
        buffer = remainder;
        messages.push(...decoded);
      });
      socket.on("error", () => finish({ messages, status: 0 }));

      for (const message of sequence) {
        socket.write(encodeFrame(message, { mask: true }));
      }
    });

    req.on("response", (res) => {
      finish({ messages: [], status: res.statusCode });
    });

    req.on("error", (err) => {
      finish({ messages, status: 0, error: err.message });
    });

    req.end();
  });
}

export default exchangeWebSocket;
