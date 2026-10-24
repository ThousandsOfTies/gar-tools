import { decodeRgb565 } from "./framebuffer.mjs";

/** Reusable T-Watch 2020 V3 peripheral surface; application and transport agnostic. */
export class GarTWatch2020 extends HTMLElement {
  static observedAttributes = ["battery", "brightness", "powered", "charging"];

  constructor() {
    super();
    this.attachShadow({ mode: "open" }).innerHTML = `
      <style>
        :host{display:block;width:340px;max-width:100%;color:#b9bfbd;--screen-size:240px}
        *{box-sizing:border-box}.watch{position:relative;width:100%;padding:65px 0}
        .strap{position:absolute;left:25%;width:50%;top:0;bottom:0;border-radius:20px;background:repeating-linear-gradient(90deg,#272c2a 0 3px,#222725 3px 7px);box-shadow:inset 0 0 0 2px #303632}
        .strap:after{content:'';position:absolute;bottom:15px;left:calc(50% - 13px);width:26px;height:9px;border-radius:6px;background:#141b17;box-shadow:0 -19px #141b17}
        .case{position:relative;margin:0 auto;width:310px;max-width:94%;padding:21px 22px 18px;background:linear-gradient(120deg,#727975,#343b37 20%,#161c19 68%,#626a64);border-radius:51px;box-shadow:0 22px 38px #1c35292b,inset 0 0 0 2px #5c655e,inset 0 0 0 6px #252c27}
        .bezel{padding:16px 10px 3px;background:#101713;border:1px solid #4b554e;border-radius:34px;box-shadow:inset 0 0 10px #000}
        .screen{position:relative;aspect-ratio:1;width:100%;overflow:hidden;border-radius:0;background:#050908;box-shadow:0 0 0 1px #000}
        canvas{display:block;width:100%;height:100%;transition:opacity .15s}.elements{position:absolute;inset:0;container-type:inline-size;transition:opacity .15s}.off{position:absolute;inset:0;z-index:1;background:#050908;display:grid;place-items:center;font:11px system-ui;letter-spacing:2px}[hidden]{display:none!important}
        .zone{position:absolute;top:0;bottom:0;width:50%;border:0;background:transparent;cursor:pointer;touch-action:none;-webkit-tap-highlight-color:transparent}.zone.left{left:0}.zone.right{right:0}
        .zone:focus-visible{outline:2px solid #b6efd5;outline-offset:-3px}.zone:active{background:#ffffff0a}.zone:disabled{cursor:default}
        .branding{text-align:center;font:8px system-ui;letter-spacing:3px;padding-top:10px;color:#87948c}
        .power{position:absolute;right:-8px;top:108px;width:13px;height:40px;background:linear-gradient(90deg,#647066,#272f28);border:1px solid #152019;border-radius:0 5px 5px 0;cursor:pointer;touch-action:none}
        .power:focus-visible{outline:3px solid #5caf81;outline-offset:3px}.power:active{transform:translateX(-2px)}
        .indicator{position:absolute;top:19px;left:calc(50% - 2px);width:4px;height:4px;border-radius:50%;background:#a8b3aa}
        @media(prefers-reduced-motion:reduce){canvas,.elements{transition:none}}
      </style>
      <div class="watch"><div class="strap"></div><div class="case">
        <i class="indicator"></i><div class="bezel"><div class="screen">
          <canvas width="240" height="240" role="img" aria-label="T-Watch display"></canvas>
          <div class="elements" hidden><slot name="screen"></slot></div>
          <div class="off" hidden>POWER OFF</div>
          <button class="zone left" aria-label="画面左側をタッチ"></button>
          <button class="zone right" aria-label="画面右側をタッチ"></button>
        </div><div class="branding">LILYGO · T-WATCH</div></div>
        <button class="power" aria-label="側面ボタン（6秒長押しで電源）" title="側面ボタン / 6秒長押し：電源"></button>
      </div></div>`;
    this.canvas = this.shadowRoot.querySelector("canvas");
    this.elements = this.shadowRoot.querySelector(".elements");
    this.screenSlot = this.shadowRoot.querySelector('slot[name="screen"]');
    this.active = null;
  }

  connectedCallback() {
    this.listeners?.abort();
    this.listeners = new AbortController();
    const options = { signal: this.listeners.signal };
    this.screenSlot.addEventListener("slotchange", () => this.sync(), options);
    this.shadowRoot.querySelectorAll("button").forEach((button) => {
      button.addEventListener(
        "pointerdown",
        (e) => {
          if (e.button !== 0 || this.active) return;
          e.preventDefault();
          button.focus({ preventScroll: true });
          button.setPointerCapture(e.pointerId);
          this.start(button, e.pointerId, e);
        },
        options,
      );
      button.addEventListener(
        "pointermove",
        (e) => {
          if (this.active?.pointer !== e.pointerId || this.active.power) return;
          this.emit("gar-touch", { phase: "move", ...this.point(e) });
        },
        options,
      );
      button.addEventListener(
        "pointerup",
        (e) => this.finish(false, e.pointerId),
        options,
      );
      button.addEventListener(
        "pointercancel",
        (e) => this.finish(true, e.pointerId),
        options,
      );
      button.addEventListener(
        "lostpointercapture",
        (e) => this.finish(true, e.pointerId),
        options,
      );
      button.addEventListener(
        "keydown",
        (e) => {
          if (!["Enter", " "].includes(e.key)) return;
          e.preventDefault();
          if (!e.repeat && !this.active) this.start(button, "keyboard");
        },
        options,
      );
      button.addEventListener(
        "keyup",
        (e) => {
          if (!["Enter", " "].includes(e.key)) return;
          e.preventDefault();
          this.finish(false, "keyboard");
        },
        options,
      );
      button.addEventListener(
        "blur",
        () => this.finish(true, "keyboard"),
        options,
      );
    });
    window.addEventListener("blur", () => this.finish(true), options);
    this.sync();
  }

  disconnectedCallback() {
    this.finish(true);
    this.listeners?.abort();
  }

  attributeChangedCallback() {
    this.sync();
  }

  get powered() {
    return this.getAttribute("powered") !== "false";
  }
  set powered(value) {
    this.setAttribute("powered", String(Boolean(value)));
  }
  get battery() {
    return this.numberAttribute("battery", 82);
  }
  set battery(value) {
    this.setAttribute("battery", String(value));
  }
  get brightness() {
    return this.numberAttribute("brightness", 85);
  }
  set brightness(value) {
    this.setAttribute("brightness", String(value));
  }
  get displayContext() {
    return this.canvas.getContext("2d");
  }

  numberAttribute(name, fallback) {
    const raw = this.getAttribute(name);
    const n = raw === null ? fallback : Number(raw);
    return Number.isFinite(n) ? Math.max(0, Math.min(100, n)) : fallback;
  }

  sync() {
    if (!this.canvas) return;
    const hasElements = this.screenSlot.assignedElements().length > 0;
    if (!this.powered || (hasElements && this.active && !this.active.power))
      this.finish(true);
    this.canvas.hidden = hasElements;
    this.canvas.style.opacity = String(this.brightness / 100);
    this.elements.hidden = !hasElements;
    this.elements.inert = !this.powered;
    this.elements.style.opacity = String(this.brightness / 100);
    this.shadowRoot.querySelector(".off").hidden = this.powered;
    this.shadowRoot.querySelectorAll(".zone").forEach((b) => {
      b.hidden = hasElements;
      b.disabled = !this.powered || hasElements;
    });
    this.emit("gar-hardware-change", {
      powered: this.powered,
      battery: this.battery,
      brightness: this.brightness,
      charging: this.hasAttribute("charging"),
    });
  }

  setScreenLabel(text) {
    this.canvas.setAttribute("aria-label", String(text));
  }

  /** ST7789 wire order is big endian by default. */
  writeFrame(bytes, { littleEndian = false } = {}) {
    this.displayContext.putImageData(
      new ImageData(decodeRgb565(bytes, littleEndian), 240, 240),
      0,
      0,
    );
  }

  point(e) {
    const rect = this.canvas.getBoundingClientRect();
    return {
      x: Math.max(
        0,
        Math.min(239, Math.floor(((e.clientX - rect.left) * 240) / rect.width)),
      ),
      y: Math.max(
        0,
        Math.min(239, Math.floor(((e.clientY - rect.top) * 240) / rect.height)),
      ),
    };
  }

  start(button, pointer, event) {
    const power = button.classList.contains("power");
    if (!power && (!this.powered || button.disabled)) return;
    const point = event
      ? this.point(event)
      : { x: button.classList.contains("left") ? 60 : 180, y: 120 };
    this.active = { power, pointer, point, at: performance.now() };
    if (power) {
      this.emit("gar-button", { button: "power", phase: "down" });
      this.powerTimer = setTimeout(() => {
        if (!this.active?.power) return;
        this.active.held = true;
        this.powered = !this.powered;
      }, 6000);
    } else this.emit("gar-touch", { phase: "start", ...point });
  }

  finish(cancelled = false, pointer) {
    const active = this.active;
    if (!active || (pointer !== undefined && active.pointer !== pointer))
      return;
    this.active = null;
    clearTimeout(this.powerTimer);
    const durationMs = Math.round(performance.now() - active.at);
    if (active.power)
      this.emit("gar-button", {
        button: "power",
        phase: cancelled ? "cancel" : "up",
        durationMs,
        held: Boolean(active.held),
      });
    else
      this.emit("gar-touch", {
        phase: cancelled ? "cancel" : "end",
        ...active.point,
        durationMs,
      });
  }

  emit(type, detail) {
    this.dispatchEvent(
      new CustomEvent(type, { detail, bubbles: true, composed: true }),
    );
  }
}

if (!customElements.get("gar-twatch-2020"))
  customElements.define("gar-twatch-2020", GarTWatch2020);
