import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { URL } from "node:url";

const packageJson = JSON.parse(readFileSync(new URL("../package.json", import.meta.url)));

test("web toolchain is declared", () => {
  assert.ok(packageJson.dependencies.react);
  assert.ok(packageJson.devDependencies.typescript);
  assert.ok(packageJson.devDependencies.vite);
});
