/**
 * gRPC client adapter for service contract fixture.
 * Uses Node.js built-in http module only (no gRPC library).
 * Implements simple request framing for the fixture's gRPC-style endpoint.
 */

import { requestHttp } from "./http-client.js";

/**
 * Call a gRPC method on the fixture server.
 * @param {object} input - { method, id? }
 * @returns {Promise<{status: {code: number, message: string}, body: object|null, trailers: object}>}
 */
export async function callGrpc({ method = "GetOrder", id = "" }) {
  const { status, headers, body } = await requestHttp({
    method: "POST",
    path: `/grpc.${method}`,
    body: { id },
  });

  return {
    status: body.status || { code: status, message: "UNKNOWN" },
    body: body.body || null,
    trailers: body.trailers || {},
  };
}

export default callGrpc;
