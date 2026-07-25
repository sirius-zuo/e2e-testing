/**
 * Service contract fixture tests.
 * Tests synchronous HTTP, GraphQL, and gRPC adapters against the fixture server.
 * Requires the fixture server to be running on port 43170.
 */

import { describe, it } from "node:test";
import assert from "node:assert";
import { requestHttp } from "../test-support/http-client.js";
import { executeGraphql } from "../test-support/graphql-client.js";
import { callGrpc } from "../test-support/grpc-client.js";

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
