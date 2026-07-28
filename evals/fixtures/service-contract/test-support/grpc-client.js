/**
 * gRPC client adapter for service contract fixture.
 * Uses Node's built-in http2 module (real HTTP/2, no ALPN/TLS needed for h2c)
 * and the fixture's hand-rolled protobuf codec — no gRPC library.
 */

import http2 from "node:http2";
import {
  encodeGetOrderRequest,
  decodeGetOrderResponse,
  frameMessage,
  unframeMessage,
} from "../src/grpc-codec.js";

const AUTHORITY = "http://127.0.0.1:43171";

/**
 * Call a gRPC method on the fixture server.
 * @param {object} input - { method, id? }
 * @returns {Promise<{status: {code: number, message: string}, body: object|null, trailers: object}>}
 */
export async function callGrpc({ method = "GetOrder", id = "" }) {
  if (method !== "GetOrder") {
    return { status: { code: 12, message: "UNIMPLEMENTED" }, body: null, trailers: {} };
  }

  const client = http2.connect(AUTHORITY);
  client.on("error", () => {});

  try {
    return await new Promise((resolve, reject) => {
      const stream = client.request({
        ":method": "POST",
        ":path": "/service.contract.OrderService/GetOrder",
        "content-type": "application/grpc+proto",
      });

      const chunks = [];
      let trailers = {};

      stream.on("data", (chunk) => chunks.push(chunk));
      stream.on("trailers", (trailerHeaders) => {
        trailers = trailerHeaders;
      });
      stream.on("end", () => {
        const framed = unframeMessage(Buffer.concat(chunks));
        const response = framed
          ? decodeGetOrderResponse(framed.payload)
          : { id: "", status: "", items: [] };
        const code = Number(trailers["grpc-status"] ?? 2);
        resolve({
          status: { code, message: trailers["grpc-message"] || (code === 0 ? "OK" : "UNKNOWN") },
          body: code === 0 ? response : null,
          trailers,
        });
      });
      stream.on("error", reject);

      stream.write(frameMessage(encodeGetOrderRequest({ id })));
      stream.end();
    });
  } finally {
    client.close();
  }
}

export default callGrpc;
