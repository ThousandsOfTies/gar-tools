import test from "node:test";
import assert from "node:assert/strict";
import { LvglSurface, createLegacyLvglAppAdapter } from "../components/lvgl-surface.mjs";

// The port uses only this small DOM contract. Frame dimensions and heap reads
// are exercised with real typed arrays, independently of a browser or WASM SDK.
function fixture(t, { width = 320, height = 170, dimensions = true, controls = true } = {}) {
  const draws = [];
  const surfaces = [];
  let now = 1000, animation;
  t.after(() => surfaces.forEach((surface) => surface.destroy()));
  class Element extends EventTarget {
    constructor(tag) {
      super();
      this.tag = tag;
      this.children = [];
      this.dataset = {};
      this.style = {};
      this.attributes = {};
    }
    matches(tag) { return this.tag === tag; }
    querySelector(selector) {
      return selector === "canvas" ? canvas : selector === "[data-lvgl-controls]" && controls ? overlay : null;
    }
    setAttribute(name, value) { this.attributes[name] = value; }
    append(child) { child.parentNode = this; this.children.push(child); }
    remove() { this.parentNode.children.splice(this.parentNode.children.indexOf(this), 1); this.parentNode = null; }
    getBoundingClientRect() { return { left: 10, top: 20, width: 640, height: 340 }; }
    getContext() { return { putImageData: (data) => draws.push(data) }; }
  }
  const globals = {
    window: new EventTarget(),
    document: Object.assign(new EventTarget(), { createElement: (tag) => new Element(tag) }),
    requestAnimationFrame: (callback) => { animation = callback; return 1; },
    cancelAnimationFrame: () => {},
    performance: { now: () => now },
    ImageData: class {
      constructor(data, width, height) { Object.assign(this, { data, width, height }); }
    },
  };
  for (const [name, value] of Object.entries(globals)) {
    const previous = Object.getOwnPropertyDescriptor(globalThis, name);
    Object.defineProperty(globalThis, name, { value, configurable: true, writable: true });
    t.after(() => previous ? Object.defineProperty(globalThis, name, previous) : delete globalThis[name]);
  }
  const element = new Element("section"), canvas = new Element("canvas"), overlay = new Element("div");
  const pointers = [];
  const ticks = [], inputTimeline = [];
  let cancellations = 0;
  const module = {
    HEAPU8: new Uint8Array(width * height * 4),
    _gar_lv_init() {},
    _gar_lv_tick(ms) { ticks.push(ms); inputTimeline.push(["tick", ms]); },
    _gar_lv_cancel() { cancellations++; },
    _gar_lv_frame: () => 0,
    _gar_lv_framebuffer: () => 0,
    _gar_lv_pointer: (...args) => { pointers.push(args); inputTimeline.push(["pointer", ...args]); },
  };
  if (dimensions) {
    module._gar_lv_width = () => width;
    module._gar_lv_height = () => height;
  }
  return { module, element, canvas, overlay, pointers, draws, surfaces, ticks, inputTimeline,
    get cancellations() { return cancellations; },
    advance(ms) { now += ms; },
    frame(timestamp = now) { animation(timestamp); },
  };
}

test("bare LVGL modules render a non-square framebuffer and scale pointer coordinates", (t) => {
  const f = fixture(t, { controls: false });
  f.module.HEAPU8.set([255, 30, 0, 255], f.module.HEAPU8.length - 4);
  const surface = new LvglSurface(f.module, f.element);
  f.surfaces.push(surface);
  assert.equal(f.canvas.width, 320);
  assert.equal(f.canvas.height, 170);
  assert.equal(f.draws[0].data.length, 320 * 170 * 4);
  assert.deepEqual([...f.draws[0].data.slice(-4)], [255, 30, 0, 255]);
  surface.pointer({ clientX: 330, clientY: 190 }, true);
  assert.deepEqual(f.pointers, [[160, 85, 1]]);
  assert.equal(f.draws.length, 1, "unchanged LVGL frame is not redrawn");
});

test("custom adapters supply geometry and app hooks without legacy exports", (t) => {
  const f = fixture(t);
  const calls = [];
  let outgoing;
  const adapter = {
    init: () => calls.push("init"),
    refresh: () => ({ label: "Thermostat", nodes: [{ id: "heat", label: "Heat", x: 160, y: 85, width: 80, height: 34 }] }),
    takeAction: () => { const action = outgoing; outgoing = null; return action; },
    receive: (message) => calls.push(message),
    hardware: (state) => calls.push(state),
    reset: () => calls.push("reset"),
  };
  const surface = new LvglSurface(f.module, f.element, { adapter });
  f.surfaces.push(surface);
  assert.equal(f.canvas.attributes["aria-label"], "Thermostat");
  assert.equal(f.overlay.children[0].style.cssText, "left:50%;top:50%;width:25%;height:20%;");
  surface.receive({ temperature: 22 });
  surface.hardware({ temperature: 24 });
  assert.equal(f.element.inert, undefined, "unrelated hardware updates do not disable the display");
  surface.reset();
  assert.deepEqual(calls, ["init", { temperature: 22 }, { temperature: 24 }, "reset"]);
  const actions = [];
  surface.addEventListener("action", (event) => actions.push(event.detail));
  outgoing = { setTemperature: 25 };
  surface.update();
  assert.deepEqual(actions, [{ setTemperature: 25 }]);
});

test("old compiled modules retain the 240 square default", (t) => {
  const f = fixture(t, { width: 240, height: 240, dimensions: false });
  const surface = new LvglSurface(f.module, f.element, { adapter: null });
  f.surfaces.push(surface);
  assert.equal(f.draws[0].width, 240);
  assert.equal(f.draws[0].height, 240);
});

test("declared dimensions cannot override a compiled module's framebuffer size", (t) => {
  const f = fixture(t);
  assert.throws(() => new LvglSurface(f.module, f.element, { width: 240 }), /must match/);
});

test("slow visible animation frames preserve elapsed time and input starts at the current clock", (t) => {
  const f = fixture(t, { controls: false });
  const surface = new LvglSurface(f.module, f.element, { adapter: null });
  f.surfaces.push(surface);
  f.advance(500);
  surface.pointer({ clientX: 330, clientY: 190 }, true);
  assert.deepEqual(f.inputTimeline, [["tick", 500], ["pointer", 160, 85, 1]],
    "idle time advances before pressing, so it cannot count toward a hold");
  f.frame(1490);
  assert.deepEqual(f.ticks, [500], "an older queued frame cannot move the input clock backwards");
  f.advance(1050);
  f.frame();
  assert.deepEqual(f.ticks, [500, 1050], "a stalled visible frame must not discard hold time");
  f.advance(950);
  surface.pointer({ clientX: 330, clientY: 190 }, false);
  assert.deepEqual(f.inputTimeline.slice(-2), [["tick", 950], ["pointer", 160, 85, 0]],
    "release samples the elapsed hold even if rendering has not resumed");
});

test("hiding cancels input and hidden time is excluded when rendering resumes", (t) => {
  const f = fixture(t, { controls: false });
  const surface = new LvglSurface(f.module, f.element, { adapter: null });
  f.surfaces.push(surface);
  surface.contact = { id: "keyboard", x: 160, y: 85 };
  f.advance(400);
  document.hidden = true;
  document.dispatchEvent(new Event("visibilitychange"));
  assert.equal(surface.contact, null);
  assert.equal(f.cancellations, 1);
  f.advance(5000);
  f.frame();
  assert.deepEqual(f.ticks, []);
  document.hidden = false;
  document.dispatchEvent(new Event("visibilitychange"));
  f.advance(16);
  f.frame();
  assert.deepEqual(f.ticks, [16], "background time does not become elapsed hold time");
});

test("legacy adapter preserves JSON messages, actions and hardware argument order", () => {
  const calls = [];
  const adapter = createLegacyLvglAppAdapter({
    _gar_app_init: () => calls.push("init"),
    _gar_app_refresh: () => calls.push("refresh"),
    _gar_app_snapshot: () => 1,
    _gar_app_take_action: () => 2,
    _gar_app_receive() {},
    _gar_app_hardware: (...args) => calls.push(args),
    UTF8ToString: (pointer) => pointer === 1 ? '{"label":"Watch"}' : '{"action":"stop"}',
    ccall: (...args) => calls.push(args),
  });
  adapter.init();
  assert.deepEqual(adapter.refresh(), { label: "Watch" });
  assert.deepEqual(adapter.takeAction(), { action: "stop" });
  adapter.receive({ connected: true });
  adapter.hardware({ powered: true, connected: true, battery: 82, charging: false, demo: false });
  assert.deepEqual(calls, ["init", "refresh", ["gar_app_receive", "number", ["string"], ['{"connected":true}']], [1, 1, 82, 0, 0]]);
});
