import "./gar-components/display.mjs";

const results = document.querySelector("#results");
const fixture = document.querySelector("#fixture");
const lines = [];
const assert = (condition, message) => { if (!condition) throw new Error(message); };
const run = (name, test) => {
  try { test(); lines.push(`PASS - ${name}`); }
  catch (error) { lines.push(`FAIL - ${name}: ${error.message}`); }
  results.textContent = lines.join("\n");
};
const keys = (display, type, repeat = false, key = " ") => display.canvas.dispatchEvent(
  new KeyboardEvent(type, { key, repeat, bubbles: true }),
);
const display = document.createElement("gar-display");
const other = document.createElement("gar-display");
fixture.append(display, other);
const events = [];
display.addEventListener("gar-touch", (event) => events.push(event));
const pixel = (target, x, y) => [...target.displayContext.getImageData(x, y, 1, 1).data];
const same = (actual, expected) => JSON.stringify(actual) === JSON.stringify(expected);

run("default dimensions and native focus accessibility are initialized", () => {
  assert(display.width === 320 && display.height === 240, "default dimensions");
  assert(display.canvas.width === 320 && display.canvas.height === 240, "canvas dimensions");
  assert(display.canvas.tabIndex === 0 && display.canvas.getAttribute("role") === "img", "focusable image");
  display.setAttribute("label", "Test pixel display");
  assert(display.canvas.getAttribute("aria-label") === "Test pixel display", "custom accessible name");
});

run("RGB565 frames render at two independent non-square dimensions", () => {
  display.width = 2;
  display.height = 3;
  other.width = 5;
  other.height = 2;
  const first = new Uint8Array(12);
  first.set([0xf8, 0x00, 0x07, 0xe0]); // big-endian red, green
  first.set([0x00, 0x1f], 10); // final pixel blue
  display.writeFrame(first);
  const second = new Uint8Array(20);
  second.set([0xff, 0xff]); // little-endian white
  second.set([0x00, 0xf8], 18); // final pixel red
  other.writeFrame(second, { littleEndian: true });
  assert(display.canvas.width === 2 && display.canvas.height === 3, "first surface dimensions");
  assert(other.canvas.width === 5 && other.canvas.height === 2, "second surface dimensions");
  assert(same(pixel(display, 0, 0), [255, 0, 0, 255]), "first red pixel");
  assert(same(pixel(display, 1, 0), [0, 255, 0, 255]), "first green pixel");
  assert(same(pixel(display, 1, 2), [0, 0, 255, 255]), "first last pixel");
  assert(same(pixel(other, 0, 0), [255, 255, 255, 255]), "second white pixel");
  assert(same(pixel(other, 4, 1), [255, 0, 0, 255]), "second last pixel");
});

run("brightness and power are isolated and preserve pixel content", () => {
  display.brightness = 38;
  assert(display.canvas.style.opacity === "0.38", "brightness opacity");
  assert(other.brightness === 100 && other.powered, "independent state");
  display.brightness = 300;
  assert(display.brightness === 100, "high brightness clamp");
  display.brightness = -2;
  assert(display.brightness === 0, "low brightness clamp");
  display.brightness = 100;
  assert(same(pixel(display, 1, 2), [0, 0, 255, 255]), "brightness erased framebuffer");
});

run("keyboard gesture emits one composed start/end pair and ignores repeat", () => {
  events.length = 0;
  keys(display, "keydown");
  keys(display, "keydown", true);
  keys(display, "keyup");
  keys(display, "keyup");
  assert(events.length === 2, `keyboard event count ${events.length}`);
  assert(events[0].detail.phase === "start" && events[1].detail.phase === "end", "gesture phases");
  assert(events[0].detail.x === 1 && events[0].detail.y === 1, "center coordinate");
  assert(events.every((event) => event.bubbles && event.composed), "public event flags");
  assert(Number.isFinite(events[1].detail.durationMs) && events[1].detail.durationMs >= 0, "gesture duration");
});

run("power off cancels active input and prevents new keyboard input", () => {
  events.length = 0;
  keys(display, "keydown");
  display.powered = false;
  assert(events.length === 2 && events[1].detail.phase === "cancel", "power cancellation");
  assert(display.canvas.style.opacity === "0" && display.canvas.tabIndex === -1, "powered-off surface");
  assert(display.canvas.getAttribute("aria-disabled") === "true", "disabled accessibility");
  keys(display, "keyup");
  keys(display, "keydown");
  keys(display, "keyup");
  assert(events.length === 2, "powered-off input emitted events");
  display.powered = true;
  assert(display.canvas.tabIndex === 0 && other.powered, "power restoration and isolation");
  assert(same(pixel(display, 1, 2), [0, 0, 255, 255]), "power erased framebuffer");
});

run("detach cancels active input and repeated reconnect does not duplicate listeners", () => {
  events.length = 0;
  keys(display, "keydown", false, "Enter");
  display.remove();
  assert(events.length === 2 && events[1].detail.phase === "cancel", "detach cancellation");
  keys(display, "keyup", false, "Enter");
  keys(display, "keydown");
  assert(events.length === 2, "detached listeners still active");
  for (let i = 0; i < 3; i++) { fixture.append(display); display.remove(); }
  fixture.append(display);
  events.length = 0;
  keys(display, "keydown", false, "Enter");
  keys(display, "keyup", false, "Enter");
  assert(events.length === 2 && events[1].detail.phase === "end", "reconnect listener count");
});

run("pointer coordinates scale independently per axis and clamp outside the canvas", () => {
  display.width = 7;
  display.height = 3;
  const rect = display.canvas.getBoundingClientRect();
  assert(rect.width > 0 && rect.height > 0, "visible canvas geometry");
  assert(same(display.point({ clientX: rect.left + rect.width / 2, clientY: rect.top + rect.height / 2 }), { x: 3, y: 1 }), "scaled center");
  assert(same(display.point({ clientX: rect.left - 100, clientY: rect.top - 100 }), { x: 0, y: 0 }), "negative clamp");
  assert(same(display.point({ clientX: rect.right + 100, clientY: rect.bottom + 100 }), { x: 6, y: 2 }), "positive clamp");
});

run("pointer release reports the final coordinate without requiring a move event", () => {
  events.length = 0;
  const rect = display.canvas.getBoundingClientRect();
  display.start(17, { x: 0, y: 0 });
  display.canvas.dispatchEvent(new PointerEvent("pointerup", {
    pointerId: 17, clientX: rect.left + rect.width * 0.75,
    clientY: rect.top + rect.height * 0.75, bubbles: true,
  }));
  assert(events.length === 2 && events[1].detail.phase === "end", "release event");
  assert(events[1].detail.x === 5 && events[1].detail.y === 2, "release used stale coordinates");
  assert(display.contact === null, "release retained contact");
});

run("blur and dimension changes cancel gestures before the next input", () => {
  events.length = 0;
  keys(display, "keydown");
  display.canvas.dispatchEvent(new Event("blur"));
  keys(display, "keyup");
  assert(events.length === 2 && events[1].detail.phase === "cancel", "blur cancellation");
  events.length = 0;
  keys(display, "keydown");
  display.width = 8;
  keys(display, "keyup");
  assert(events.length === 2 && events[1].detail.phase === "cancel", "resize cancellation");
  assert(display.canvas.width === 8 && other.canvas.width === 5, "resize isolation");
});

const passed = lines.filter((line) => line.startsWith("PASS")).length;
results.textContent += `\n\n${passed}/${lines.length} passed`;
document.title = `${passed === lines.length ? "PASS" : "FAIL"} - Generic display tests`;
document.documentElement.dataset.testResult = passed === lines.length ? "pass" : "fail";
