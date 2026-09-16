import assert from "node:assert/strict";
import test from "node:test";

import { resolveGameLang } from "../src/gameLanguage.ts";

test("Chinese UI defaults to English game language", () => {
  assert.equal(resolveGameLang("zh"), "en");
});

test("explicit game language overrides the UI fallback", () => {
  assert.equal(resolveGameLang("zh", "zh"), "zh");
  assert.equal(resolveGameLang("ko", "zh"), "zh");
});
