/**
 * Service contract fixture server.
 * Provides HTTP REST, GraphQL, and gRPC-style endpoints using Node.js built-ins only.
 * All data is disposable and held in memory.
 */

import http from "node:http";
import { createHash } from "node:crypto";
import { encodeFrame, decodeFrames } from "./ws-frames.js";

const PORT = 43170;
const HOST = "127.0.0.1";

// Disposable orders in memory
const orders = new Map([
  ["order-1", { id: "order-1", status: "accepted", items: ["item-a"] }],
  ["order-2", { id: "order-2", status: "pending", items: ["item-b"] }],
]);

// GraphQL schema (simplified)
const graphqlTypes = {
  Order: {
    __typename: "Order",
    id: String,
    status: String,
    items: [String],
  },
};

// gRPC-style service methods
const grpcMethods = new Map([
  ["GetOrder", { request: { id: String }, response: { status: { code: Number }, body: Object } }],
]);

// WebSocket subscriptions (in-memory)
const wsSubscriptions = new Map();
const wsMessages = [];

// Queue in-memory store
const queueStore = new Map();

// Stream in-memory store
const streamStore = new Map();

function jsonResponse(res, statusCode, body, extraHeaders = {}) {
  const payload = JSON.stringify(body);
  const headers = {
    "Content-Type": "application/json",
    "Content-Length": Buffer.byteLength(payload),
    ...extraHeaders,
  };
  res.writeHead(statusCode, headers);
  res.end(payload);
}

function graphqlHandler(req, res, query, variables = {}) {
  // Simple GraphQL executor
  const data = {};
  const errors = [];

  // Parse operation name
  const match = query.match(/query\s+(\w+)/);
  const operationName = match ? match[1] : null;

  if (operationName === "Order" || query.includes("Order")) {
    const id = variables.id || (query.match(/id:\s*["']([^"']+)["']/) || [])[1];
    if (id) {
      const order = orders.get(id);
      if (order) {
        data.order = { ...order, __typename: "Order" };
      } else {
        errors.push({ message: `Order ${id} not found`, path: ["order"] });
      }
    } else {
      errors.push({ message: "Missing required variable: id" });
    }
  } else if (query.includes("orders")) {
    data.orders = Array.from(orders.values()).map((o) => ({ ...o, __typename: "Order" }));
  } else {
    errors.push({ message: `Unknown operation: ${operationName || "unknown"}` });
  }

  const response = {};
  if (Object.keys(data).length > 0) response.data = data;
  if (errors.length > 0) response.errors = errors;

  jsonResponse(res, 200, response);
}

function grpcHandler(req, res) {
  // Simple gRPC-style framing using HTTP/2-like approach with headers
  // URL is like "/grpc.GetOrder", extract "GetOrder"
  const fullMethod = req.url?.split("/")?.[1] || "";
  const method = fullMethod.startsWith("grpc.") ? fullMethod.slice(5) : fullMethod;
  const bodyRaw = req.body || "{}";

  let parsedBody;
  try {
    parsedBody = JSON.parse(bodyRaw);
  } catch {
    parsedBody = {};
  }

  if (method === "GetOrder") {
    const orderId = parsedBody.id || "";
    const order = orders.get(orderId);
    if (order) {
      jsonResponse(res, 200, {
        status: { code: 0, message: "OK" },
        body: { ...order, __typename: "Order" },
        trailers: { "grpc-status-details-bin": "" },
      });
    } else {
      jsonResponse(res, 200, {
        status: { code: 5, message: "NOT_FOUND" },
        body: null,
        trailers: { "grpc-status-details-bin": JSON.stringify([{ reason: "ORDER_NOT_FOUND" }]) },
      });
    }
  } else {
    jsonResponse(res, 200, {
      status: { code: 12, message: "UNIMPLEMENTED" },
      body: null,
      trailers: {},
    });
  }
}

const server = http.createServer(async (req, res) => {
  // Read request body
  let bodyRaw = "";
  for await (const chunk of req) {
    bodyRaw += chunk;
  }
  req.body = bodyRaw;

  const url = new URL(req.url || "/", `http://${HOST}:${PORT}`);
  const path = url.pathname;

  // Health check
  if (path === "/health") {
    jsonResponse(res, 200, { status: "ok", fixture: "service-contract" });
    return;
  }

  // REST order endpoint
  if (path.startsWith("/orders/") && req.method === "GET") {
    const orderId = path.split("/")[2];
    const order = orders.get(orderId);
    if (order) {
      jsonResponse(res, 200, { ...order, __typename: "Order" });
    } else {
      jsonResponse(res, 404, { error: `Order ${orderId} not found` });
    }
    return;
  }

  // GraphQL endpoint
  if (path === "/graphql" && req.method === "POST") {
    try {
      const parsed = JSON.parse(bodyRaw);
      graphqlHandler(req, res, parsed.query || "", parsed.variables || {});
    } catch {
      jsonResponse(res, 400, { errors: [{ message: "Invalid JSON" }] });
    }
    return;
  }

  // gRPC-style endpoint
  if (path.startsWith("/grpc.") && req.method === "POST") {
    grpcHandler(req, res);
    return;
  }

  // Queue publish
  if (path === "/queue/publish" && req.method === "POST") {
    try {
      const msg = JSON.parse(bodyRaw);
      queueStore.set(msg.correlationId, {
        message: msg,
        delivered: true,
        acknowledged: false,
        redeliveryCount: 0,
      });
      jsonResponse(res, 200, { delivered: true, correlationId: msg.correlationId });
    } catch {
      jsonResponse(res, 400, { error: "Invalid message" });
    }
    return;
  }

  // Queue consume
  if (path === "/queue/consume" && req.method === "POST") {
    try {
      const { correlationId, acknowledge } = JSON.parse(bodyRaw);
      const item = queueStore.get(correlationId);
      if (item) {
        item.acknowledged = acknowledge === true;
        jsonResponse(res, 200, {
          message: item.message,
          acknowledged: item.acknowledged,
          redeliveryCount: item.redeliveryCount,
        });
      } else {
        jsonResponse(res, 404, { error: "No message for correlationId" });
      }
    } catch {
      jsonResponse(res, 400, { error: "Invalid request" });
    }
    return;
  }

  // Stream append
  if (path === "/stream/append" && req.method === "POST") {
    try {
      const event = JSON.parse(bodyRaw);
      streamStore.set(event.correlationId, {
        event,
        committed: false,
        partition: 0,
        offset: streamStore.size,
      });
      jsonResponse(res, 200, { appended: true, correlationId: event.correlationId });
    } catch {
      jsonResponse(res, 400, { error: "Invalid event" });
    }
    return;
  }

  // Stream read
  if (path === "/stream/read" && req.method === "POST") {
    try {
      const { correlationId, commit } = JSON.parse(bodyRaw);
      const item = streamStore.get(correlationId);
      if (item) {
        if (commit) item.committed = true;
        jsonResponse(res, 200, {
          event: item.event,
          cursorCommitted: commit === true ? true : item.committed,
          partition: item.partition,
          offset: item.offset,
        });
      } else {
        jsonResponse(res, 404, { error: "No event for correlationId" });
      }
    } catch {
      jsonResponse(res, 400, { error: "Invalid request" });
    }
    return;
  }

  // Default 404
  jsonResponse(res, 404, { error: "Not found", path });
});

server.listen(PORT, HOST, () => {
  console.log(`Service contract fixture listening on ${HOST}:${PORT}`);
});

// Real WebSocket upgrade (RFC 6455): Node only emits 'upgrade', never 'request', for these.
server.on("upgrade", (req, socket, head) => {
  const url = new URL(req.url || `/`, `http://${HOST}:${PORT}`);
  const key = req.headers["sec-websocket-key"];
  if (url.searchParams.get("ws") !== "true" || (req.headers.upgrade || "").toLowerCase() !== "websocket" || !key) {
    socket.destroy();
    return;
  }

  const accept = createHash("sha1")
    .update(key + "258EAFA5-E914-47DA-95CA-5AB9D8B23D4E")
    .digest("base64");
  socket.write(
    [
      "HTTP/1.1 101 Switching Protocols",
      "Upgrade: websocket",
      "Connection: Upgrade",
      `Sec-WebSocket-Accept: ${accept}`,
      "Sec-WebSocket-Protocol: e2e-v1",
      "\r\n",
    ].join("\r\n")
  );

  let buffer = head && head.length ? Buffer.from(head) : Buffer.alloc(0);
  socket.on("data", (chunk) => {
    buffer = Buffer.concat([buffer, chunk]);
    const { messages, remainder } = decodeFrames(buffer);
    buffer = remainder;
    for (const message of messages) {
      if (message.__close) {
        socket.end();
        return;
      }
      if (message.type === "subscribe" && typeof message.orderId === "string" && message.orderId) {
        const order = orders.get(message.orderId);
        socket.write(
          encodeFrame(
            {
              type: "notification",
              correlationId: message.orderId,
              data: order ? { ...order, __typename: "Order" } : { error: `Order ${message.orderId} not found` },
            },
            { mask: false }
          )
        );
      }
    }
  });
  socket.on("error", () => socket.destroy());
});

// Graceful shutdown
process.on("SIGTERM", () => {
  server.close(() => process.exit(0));
});
process.on("SIGINT", () => {
  server.close(() => process.exit(0));
});

export default server;
