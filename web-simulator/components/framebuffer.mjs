/** Convert RGB565 to RGBA without the DOM. The legacy boolean argument and
 * 240 × 240 defaults remain supported; other displays pass an options object. */
export function decodeRgb565(bytes, options = false) {
  const { width = 240, height = 240, littleEndian = false } =
    typeof options === "boolean" ? { littleEndian: options } : options ?? {};
  const pixels = width * height;
  if (
    !Number.isSafeInteger(width) || width <= 0 ||
    !Number.isSafeInteger(height) || height <= 0 ||
    !Number.isSafeInteger(pixels * 4)
  ) {
    throw new RangeError("Frame dimensions must be positive safe integers.");
  }
  if (!(bytes instanceof Uint8Array) || bytes.length !== pixels * 2) {
    throw new RangeError(
      `A ${width} × ${height} RGB565 frame must contain exactly ${pixels * 2} bytes.`,
    );
  }
  const rgba = new Uint8ClampedArray(pixels * 4);
  for (let p = 0; p < pixels; p++) {
    const value = littleEndian
      ? bytes[p * 2] | (bytes[p * 2 + 1] << 8)
      : (bytes[p * 2] << 8) | bytes[p * 2 + 1];
    rgba[p * 4] = Math.round((((value >> 11) & 31) * 255) / 31);
    rgba[p * 4 + 1] = Math.round((((value >> 5) & 63) * 255) / 63);
    rgba[p * 4 + 2] = Math.round(((value & 31) * 255) / 31);
    rgba[p * 4 + 3] = 255;
  }
  return rgba;
}
