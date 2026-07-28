/**
 * HTTP client adapter for service contract fixture.
 * Uses Node.js built-in http module only.
 */

import http from "node:http";

const BASE_URL = "http://127.0.0.1:43170";

/**
 * Make an HTTP request to the fixture server.
 * @param {object} input - { method, path, body? }
 * @returns {Promise<{status: number, headers: object, body: object}>}
 */
export async function requestHttp({ method = "GET", path = "/health", body }) {
  const url = `${BASE_URL}${path}`;
  return new Promise((resolve, reject) => {
    const options = {
      method,
      headers: { "Content-Type": "application/json" },
      timeout: 5000,
    };
    if (body) {
      options.headers["Content-Length"] = Buffer.byteLength(JSON.stringify(body));
    }

    const req = http.request(url, options, (res) => {
      let data = "";
      res.on("data", (chunk) => {
        data += chunk;
      });
      res.on("end", () => {
        try {
          const parsed = JSON.parse(data);
          resolve({
            status: res.statusCode,
            headers: { "content-type": res.headers["content-type"] || "application/json" },
            body: parsed,
          });
        } catch {
          resolve({
            status: res.statusCode,
            headers: { "content-type": res.headers["content-type"] || "application/json" },
            body: data,
          });
        }
      });
    });

    req.on("error", reject);
    req.on("timeout", () => {
      req.destroy();
      reject(new Error("HTTP request timed out"));
    });

    if (body) {
      req.write(JSON.stringify(body));
    }
    req.end();
  });
}

export default requestHttp;
