import assert from "node:assert/strict";
import test from "node:test";
import { ApiClient, ApiError } from "../src/api-client.ts";

const DEVICE_ID = "dca0bc53-11e2-4709-9f8d-d2fd266cb02f";

test("web login sends matching device headers and persists access token", async () => {
  const calls = [];
  const client = new ApiClient(DEVICE_ID, async (url, init) => {
    calls.push({ url, init });
    return new globalThis.Response(
      JSON.stringify({ access_token: "token", user: { id: "u", role: "logistician" } }),
      { status: 200 },
    );
  });
  const user = await client.login("+79990000000", "secret");
  assert.equal(user.role, "logistician");
  assert.equal(client.getAccessToken(), "token");
  assert.equal(calls[0].url, "/api/v1/auth/login");
  assert.equal(calls[0].init.headers["X-Platform"], "web");
  assert.equal(calls[0].init.headers["X-Device-Id"], DEVICE_ID);
  assert.equal(JSON.parse(calls[0].init.body).device.platform, "web");
  await client.orders();
  assert.equal(calls[1].init.headers.Authorization, "Bearer token");
});

test("API errors retain status and trace ID without exposing request data", async () => {
  const client = new ApiClient(
    DEVICE_ID,
    async () =>
      new globalThis.Response(JSON.stringify({ error: "Access denied", trace_id: "tr-1" }), {
        status: 403,
      }),
  );
  await assert.rejects(client.orders(), (error) => {
    assert.ok(error instanceof ApiError);
    assert.equal(error.status, 403);
    assert.equal(error.traceId, "tr-1");
    return true;
  });
});
