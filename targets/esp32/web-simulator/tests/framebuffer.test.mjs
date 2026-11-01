import test from "node:test";
import assert from "node:assert/strict";
import { decodeRgb565 } from "../components/framebuffer.mjs";

test("ST7789 wire bytes decode black, red, green, blue and white at full intensity", () => {
  const bytes = new Uint8Array(115200);
  bytes.set([0, 0, 0xf8, 0, 7, 0xe0, 0, 0x1f, 0xff, 0xff]);
  assert.deepEqual(
    Array.from(decodeRgb565(bytes).slice(0, 20)),
    [
      0, 0, 0, 255, 255, 0, 0, 255, 0, 255, 0, 255, 0, 0, 255, 255, 255, 255,
      255, 255,
    ],
  );
});
test("host little-endian frame is supported without changing the input", () => {
  const bytes = new Uint8Array(115200);
  bytes.set([0, 0xf8]);
  assert.deepEqual(
    Array.from(decodeRgb565(bytes, true).slice(0, 4)),
    [255, 0, 0, 255],
  );
  assert.equal(bytes[0], 0);
});
test("truncated, oversized and untyped frames are rejected", () => {
  for (const bytes of [
    new Uint8Array(115198),
    new Uint8Array(115202),
    "pixels",
    null,
  ])
    assert.throws(() => decodeRgb565(bytes), RangeError);
});

test("non-square displays decode their complete RGB565 frame", () => {
  const bytes = new Uint8Array(320 * 170 * 2);
  bytes.set([0xf8, 0]);
  bytes.set([0, 0x1f], bytes.length - 2);
  const rgba = decodeRgb565(bytes, { width: 320, height: 170 });
  assert.equal(rgba.length, 320 * 170 * 4);
  assert.deepEqual([...rgba.slice(0, 4)], [255, 0, 0, 255]);
  assert.deepEqual([...rgba.slice(-4)], [0, 0, 255, 255]);
  assert.throws(() => decodeRgb565(bytes), RangeError);
});

test("custom display options support little-endian input", () => {
  assert.deepEqual(
    [...decodeRgb565(new Uint8Array([0xe0, 7]), { width: 1, height: 1, littleEndian: true })],
    [0, 255, 0, 255],
  );
});

test("invalid or unsafe dimensions cannot allocate a frame", () => {
  for (const width of [0, -1, 1.5, NaN, Infinity, Number.MAX_SAFE_INTEGER])
    assert.throws(() => decodeRgb565(new Uint8Array(0), { width, height: 2 }), RangeError);
});
