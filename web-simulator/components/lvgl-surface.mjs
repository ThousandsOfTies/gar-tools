/** Compatibility adapter for the original gar_app_* exports. New applications
 * can pass their own adapter, or null for a framebuffer/pointer-only surface. */
export function createLegacyLvglAppAdapter(module) {
  const readJson = (name, fallback) => {
    const pointer = module[name]?.();
    return pointer ? JSON.parse(module.UTF8ToString(pointer) || "null") : fallback;
  };
  return {
    init: () => module._gar_app_init?.(),
    refresh: () => {
      module._gar_app_refresh?.();
      return readJson("_gar_app_snapshot", {});
    },
    takeAction: () => readJson("_gar_app_take_action", null),
    receive: (message) => {
      if (module._gar_app_receive)
        module.ccall("gar_app_receive", "number", ["string"], [JSON.stringify(message)]);
    },
    reset: () => module._gar_app_reset?.(),
    hardware: ({ powered, connected, battery, charging, demo }) =>
      module._gar_app_hardware?.(
        Number(powered), Number(connected), battery, Number(charging), Number(demo),
      ),
    sideButton: () => module._gar_app_side_button?.(),
    scroll: module._gar_app_scroll ? (delta) => module._gar_app_scroll(delta) : undefined,
  };
}

/** Display a compiled LVGL UI at its exported width and height (legacy: 240 × 240).
 * Optional adapter hooks: init, refresh -> {label,nodes}, takeAction -> action,
 * receive(message), reset, hardware(state), sideButton, scroll(delta).
 * Nodes use LVGL pixel coordinates. DOM controls mirror their geometry, while
 * input returns to LVGL's pointer driver and original event callbacks. */
export class LvglSurface extends EventTarget {
  constructor(module, element, settings = {}) {
    super();
    this.module = module;
    this.element = element;
    this.canvas = element.matches?.("canvas") ? element : element.querySelector("canvas");
    if (!this.canvas) throw new TypeError("LvglSurface requires a canvas.");
    this.controls = element.querySelector("[data-lvgl-controls]");
    this.context = this.canvas.getContext("2d");
    this.width = module._gar_lv_width?.() ?? settings.width ?? 240;
    this.height = module._gar_lv_height?.() ?? settings.height ?? 240;
    if (!Number.isSafeInteger(this.width) || this.width <= 0 ||
        !Number.isSafeInteger(this.height) || this.height <= 0 ||
        !Number.isSafeInteger(this.width * this.height * 4))
      throw new RangeError("Display dimensions must be positive safe integers.");
    if ((settings.width !== undefined && settings.width !== this.width) ||
        (settings.height !== undefined && settings.height !== this.height))
      throw new RangeError("Display dimensions must match the compiled LVGL module.");
    this.canvas.width = this.width;
    this.canvas.height = this.height;
    this.adapter = settings.adapter === undefined
      ? createLegacyLvglAppAdapter(module) : settings.adapter;
    this.nodes = [];
    this.contact = null;
    this.frame = -1;
    this.nodeKey = "";
    this.listeners = new AbortController();
    const options = { signal: this.listeners.signal };
    module._gar_lv_init();
    this.adapter?.init?.();
    this.lastTick = performance.now();
    element.addEventListener(
      "pointerdown",
      (event) => {
        if (
          event.button !== 0 ||
          !event.isPrimary ||
          this.contact ||
          element.inert
        )
          return;
        event.preventDefault();
        event.target.closest("button")?.focus({ preventScroll: true });
        element.setPointerCapture(event.pointerId);
        this.contact = { id: event.pointerId };
        this.pointer(event, true);
      },
      options,
    );
    element.addEventListener(
      "pointermove",
      (event) => {
        if (this.contact?.id === event.pointerId) this.pointer(event, true);
      },
      options,
    );
    element.addEventListener(
      "pointerup",
      (event) => {
        if (this.contact?.id !== event.pointerId) return;
        this.contact = null;
        this.pointer(event, false);
      },
      options,
    );
    for (const type of ["pointercancel", "lostpointercapture"])
      element.addEventListener(
        type,
        (event) => {
          if (this.contact?.id === event.pointerId) this.cancel();
        },
        options,
      );
    element.addEventListener(
      "wheel",
      (event) => {
        if (element.inert || !this.adapter?.scroll) return;
        event.preventDefault();
        this.cancel();
        this.adapter.scroll(Math.sign(event.deltaY) * 28);
        this.update();
      },
      { ...options, passive: false },
    );
    element.addEventListener(
      "keydown",
      (event) => {
        const button = event.target.closest("button");
        if (element.inert || !button || ![" ", "Enter"].includes(event.key)) return;
        event.preventDefault();
        if (event.repeat || this.contact) return;
        const node = this.nodes.find(
          (node) => node.id === button.dataset.nodeId,
        );
        if (!node) return;
        this.advanceClock();
        this.contact = {
          id: "keyboard",
          x: node.x + node.width / 2,
          y: node.y + node.height / 2,
        };
        module._gar_lv_pointer(this.contact.x, this.contact.y, 1);
        this.update();
      },
      options,
    );
    element.addEventListener(
      "keyup",
      (event) => {
        if (
          ![" ", "Enter"].includes(event.key) ||
          this.contact?.id !== "keyboard"
        )
          return;
        event.preventDefault();
        const contact = this.contact;
        this.contact = null;
        this.advanceClock();
        module._gar_lv_pointer(contact.x, contact.y, 0);
        this.update();
      },
      options,
    );
    element.addEventListener(
      "focusout",
      () => {
        if (this.contact?.id === "keyboard") this.cancel();
      },
      options,
    );
    element.addEventListener(
      "click",
      (event) => {
        // Accessibility activation may arrive without any pointer/keyboard events.
        if (element.inert || event.detail !== 0 || this.contact) return;
        const node = this.nodes.find(
          (node) => node.id === event.target.closest("button")?.dataset.nodeId,
        );
        if (!node) return;
        const x = node.x + node.width / 2,
          y = node.y + node.height / 2;
        this.advanceClock();
        module._gar_lv_pointer(x, y, 1);
        module._gar_lv_pointer(x, y, 0);
        this.update();
      },
      options,
    );
    window.addEventListener("blur", () => this.cancel(), options);
    document.addEventListener(
      "visibilitychange",
      () => {
        // Hidden time is suspended; it must not become a hold on return.
        this.lastTick = performance.now();
        if (document.hidden) this.cancel();
      },
      options,
    );
    const tick = (now) => {
      this.advanceClock(now);
      this.update();
      this.animation = requestAnimationFrame(tick);
    };
    this.animation = requestAnimationFrame(tick);
    this.update();
  }
  advanceClock(now = performance.now()) {
    if (document.hidden) {
      this.lastTick = Math.max(this.lastTick, now);
      return;
    }
    // Preserve fractional milliseconds and all visible elapsed time even when
    // rendering is throttled. Input handlers synchronize before changing state
    // so a new press cannot inherit time from the preceding idle frame.
    const elapsed = Math.max(0, Math.floor(now - this.lastTick));
    if (elapsed > 0) {
      this.lastTick += elapsed;
      this.module._gar_lv_tick(elapsed);
    }
  }
  pointer(event, down) {
    const rect = this.canvas.getBoundingClientRect();
    this.advanceClock();
    this.module._gar_lv_pointer(
      Math.floor(((event.clientX - rect.left) * this.width) / rect.width),
      Math.floor(((event.clientY - rect.top) * this.height) / rect.height),
      Number(down),
    );
    this.update();
  }
  cancel() {
    this.contact = null;
    this.module._gar_lv_cancel();
  }
  receive(message) {
    this.adapter?.receive?.(message);
    this.update();
  }
  reset() {
    this.cancel();
    this.adapter?.reset?.();
    this.update();
  }
  hardware(state) {
    if (state.powered === false || state.connected === false) this.cancel();
    if (state.powered !== undefined) this.element.inert = !state.powered;
    this.adapter?.hardware?.(state);
    this.update();
  }
  sideButton() {
    this.adapter?.sideButton?.();
    this.update();
  }
  update() {
    const outgoing = this.adapter?.takeAction?.();
    this.snapshot = this.adapter?.refresh?.() ?? {};
    this.nodes = this.snapshot.nodes || [];
    if (this.snapshot.label !== undefined)
      this.canvas.setAttribute("aria-label", this.snapshot.label);
    const key = JSON.stringify(this.nodes);
    if (this.controls && this.nodeKey !== key) {
      const existing = new Map(
        [...this.controls.children].map((button) => [
          button.dataset.nodeId,
          button,
        ]),
      );
      for (const node of this.nodes) {
        const button =
          existing.get(node.id) || document.createElement("button");
        existing.delete(node.id);
        button.type = "button";
        button.dataset.nodeId = node.id;
        if (node.actionId !== undefined) button.dataset.actionId = node.actionId;
        else delete button.dataset.actionId;
        button.setAttribute("aria-label", node.label);
        button.style.cssText = `left:${(node.x * 100) / this.width}%;top:${(node.y * 100) / this.height}%;width:${(node.width * 100) / this.width}%;height:${(node.height * 100) / this.height}%;`;
        if (!button.parentNode) this.controls.append(button);
      }
      for (const button of existing.values()) button.remove();
      this.nodeKey = key;
    }
    const frame = this.module._gar_lv_frame();
    if (frame !== this.frame) {
      const pixels = new Uint8ClampedArray(
        this.module.HEAPU8.buffer,
        this.module._gar_lv_framebuffer(),
        this.width * this.height * 4,
      );
      this.context.putImageData(new ImageData(pixels, this.width, this.height), 0, 0);
      this.frame = frame;
    }
    if (outgoing !== undefined && outgoing !== null)
      this.dispatchEvent(
        new CustomEvent("action", { detail: outgoing }),
      );
  }
  destroy() {
    this.cancel();
    cancelAnimationFrame(this.animation);
    this.listeners.abort();
  }
}
