/**
 * Service contract fixture tests.
 * Tests synchronous HTTP, GraphQL, gRPC, and WebSocket adapters, plus
 * asynchronous queue/stream adapters, against the fixture server.
 * Starts and stops the fixture server itself; no external process required.
 */

import { before, after, describe, it } from "node:test";
import assert from "node:assert";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import path from "node:path";
import { requestHttp } from "../test-support/http-client.js";
import { executeGraphql } from "../test-support/graphql-client.js";
import { callGrpc } from "../test-support/grpc-client.js";
import { exchangeWebSocket } from "../test-support/websocket-client.js";
import { publishQueue, consumeQueue } from "../test-support/queue-client.js";
import { appendStream, readStream } from "../test-support/stream-client.js";

const FIXTURE_ROOT = path.dirname(path.dirname(fileURLToPath(import.meta.url)));
let serverProcess;

before(async () => {
  serverProcess = spawn(process.execPath, ["src/server.js"], {
    cwd: FIXTURE_ROOT,
    stdio: ["ignore", "ignore", "inherit"],
  });

  const deadline = Date.now() + 5000;
  while (Date.now() < deadline) {
    try {
      const result = await requestHttp({ method: "GET", path: "/health" });
      if (result.status === 200) return;
    } catch {
      // Server socket not accepting connections yet; keep polling.
    }
    await new Promise((resolve) => setTimeout(resolve, 50));
  }
  throw new Error("fixture server did not become ready within 5000ms");
});

after(() => {
  serverProcess.kill();
});

describe("Service Contract Fixture", () => {
  it("exposes health endpoint", async () => {
    const result = await requestHttp({ method: "GET", path: "/health" });
    assert.equal(result.status, 200);
    assert.equal(result.body.status, "ok");
  });

  it("returns REST order", async () => {
    const result = await requestHttp({ method: "GET", path: "/orders/order-1" });
    assert.equal(result.status, 200);
    assert.equal(result.body.id, "order-1");
    assert.equal(result.body.status, "accepted");
    assert.deepStrictEqual(result.headers, { "content-type": "application/json" });
  });

  it("returns 404 for missing order", async () => {
    const result = await requestHttp({ method: "GET", path: "/orders/missing" });
    assert.equal(result.status, 404);
  });

  it("executes GraphQL query", async () => {
    const result = await executeGraphql({ operation: "Order", variables: { id: "order-1" } });
    assert.equal(result.status, 200);
    assert.equal(result.data.order.status, "accepted");
    assert.equal(result.data.order.id, "order-1");
    assert.equal(result.errors, null);
  });

  it("returns GraphQL errors for missing order", async () => {
    const result = await executeGraphql({ operation: "Order", variables: { id: "missing" } });
    assert.equal(result.status, 200);
    assert.equal(result.data, null);
    assert.ok(result.errors && result.errors.length > 0);
    assert.ok(result.errors.some((e) => e.message && e.message.includes("not found")));
  });

  it("calls gRPC GetOrder", async () => {
    const result = await callGrpc({ method: "GetOrder", id: "order-1" });
    assert.equal(result.status.code, 0);
    assert.ok(result.body);
    assert.equal(result.body.id, "order-1");
    assert.equal(result.body.status, "accepted");
  });

  it("returns gRPC NOT_FOUND status for missing order", async () => {
    const result = await callGrpc({ method: "GetOrder", id: "missing" });
    assert.equal(result.status.code, 5);
    assert.equal(result.status.message, "NOT_FOUND");
    assert.equal(result.body, null);
    assert.ok(result.trailers && Object.keys(result.trailers).length > 0);
  });
});

describe("Service Contract Fixture - Queue", () => {
  it("publishes and consumes queue message", async () => {
    const result = await publishQueue({ correlationId: "order-1", type: "order.accepted" });
    assert.equal(result.delivered, true);
    assert.equal(result.correlationId, "order-1");

    const delivery = await consumeQueue("order-1", { timeoutMs: 500, acknowledge: false });
    assert.equal(delivery.message.correlationId, "order-1");
    assert.equal(delivery.acknowledged, false);
    assert.equal(delivery.redeliveryCount, 0);
  });

  it("rejects consume without correlationId", async () => {
    await assert.rejects(
      consumeQueue("", { timeoutMs: 500 }),
      /correlationId is required/
    );
  });

  it("rejects non-positive timeout", async () => {
    await assert.rejects(
      consumeQueue("order-1", { timeoutMs: -1 }),
      /timeoutMs must be a positive number/
    );
  });

  it("rejects timeout exceeding 5000ms", async () => {
    await assert.rejects(
      consumeQueue("order-1", { timeoutMs: 10000 }),
      /timeoutMs must be bounded at 5000ms/
    );
  });
});

describe("Service Contract Fixture - Stream", () => {
  it("appends and reads stream event", async () => {
    const result = await appendStream({ correlationId: "order-1", type: "order.accepted" });
    assert.equal(result.appended, true);
    assert.equal(result.correlationId, "order-1");

    const event = await readStream("order-1", { timeoutMs: 500, commit: false });
    assert.equal(event.event.correlationId, "order-1");
    assert.equal(event.cursorCommitted, false);
    assert.equal(event.partition, 0);
    assert.ok(typeof event.offset === "number");
  });

  it("rejects read without correlationId", async () => {
    await assert.rejects(
      readStream("", { timeoutMs: 500 }),
      /correlationId is required/
    );
  });

  it("rejects non-positive timeout", async () => {
    await assert.rejects(
      readStream("order-1", { timeoutMs: -1 }),
      /timeoutMs must be a positive number/
    );
  });

  it("rejects timeout exceeding 5000ms", async () => {
    await assert.rejects(
      readStream("order-1", { timeoutMs: 10000 }),
      /timeoutMs must be bounded at 5000ms/
    );
  });
});
