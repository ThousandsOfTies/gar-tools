/** Board-independent rotary encoder input and counter display. */
export class GarRotary extends HTMLElement {
  static observedAttributes = ["label", "value", "press-label", "steps-per-turn", "disabled"];
  #listeners;
  #angle = 0;
  #wheel = 0;

  constructor() {
    super();
    this.attachShadow({ mode: "open" }).innerHTML = `
      <style>
        :host { display: block; color: var(--gar-component-text, #e9f3f8); font: inherit; }
        * { box-sizing: border-box; }
        section { display: grid; gap: 12px; padding: 16px; border: 1px solid var(--gar-component-border, #285267); border-radius: 12px; background: var(--gar-component-panel, #0c1e2a); }
        .label { color: var(--gar-component-accent, #52d6c4); font-size: .72rem; letter-spacing: .12em; }
        output { color: var(--gar-component-reading, #e7f5fa); font-size: 3rem; font-variant-numeric: tabular-nums; }
        .body { display: flex; align-items: center; flex-wrap: wrap; gap: 20px; }
        .scale { padding: 10px; border-radius: 50%; background: repeating-conic-gradient(from -1deg, var(--gar-component-muted, #92aab8) 0deg 2deg, transparent 2deg var(--tick-angle, 15deg)); }
        .knob { display: grid; place-items: center; width: 96px; height: 96px; padding: 0; border-radius: 50%; border: 5px solid #415362; background: radial-gradient(circle at 35% 25%, #71838e, #202e39 70%); box-shadow: 0 4px 8px #0005; }
        .dial { display: block; position: relative; width: 100%; height: 100%; border-radius: 50%; transition: transform .1s ease-out; pointer-events: none; }
        .dial::before { content: ''; position: absolute; top: 7px; left: calc(50% - 2px); width: 4px; height: 23px; border-radius: 2px; background: var(--gar-component-accent, #52d6c4); }
        .knob:active { box-shadow: inset 0 2px 7px #0007; }
        .reading { display: grid; gap: 3px; }
        .hint, .unit { color: var(--gar-component-muted, #92aab8); font-size: .75rem; line-height: 1.5; }
        .hint { margin: 0; }
        .actions { display: grid; grid-template-columns: repeat(3, 1fr); gap: 8px; }
        button { padding: 10px; border: 1px solid var(--gar-component-border, #285267); border-radius: 6px; color: inherit; background: var(--gar-component-button, #203b59); cursor: pointer; font: inherit; }
        button:hover { border-color: var(--gar-component-accent, #52d6c4); }
        button:focus-visible { outline: 2px solid var(--gar-component-accent, #52d6c4); outline-offset: 3px; }
        button:disabled { cursor: not-allowed; opacity: .45; }
        @media (prefers-reduced-motion: reduce) { .dial { transition: none; } }
      </style>
      <section>
        <span class="label" data-label></span>
        <div class="body">
          <div class="scale"><button class="knob" type="button" aria-label="Press rotary encoder" aria-describedby="knob-help"><span class="dial" aria-hidden="true"></span></button></div>
          <div class="reading"><output data-value aria-live="polite">0</output><span class="unit">COUNTER</span></div>
        </div>
        <div class="actions">
          <button type="button" data-direction="-1" aria-label="Rotate counter-clockwise">-</button>
          <button type="button" data-direction="1" aria-label="Rotate clockwise">+</button>
          <button type="button" data-press></button>
        </div>
        <p class="hint" id="knob-help">− / +: rotate · PRESS: push<br>Focus knob: arrow keys or mouse wheel</p>
      </section>`;
    this._label = this.shadowRoot.querySelector("[data-label]");
    this._value = this.shadowRoot.querySelector("[data-value]");
    this._press = this.shadowRoot.querySelector("[data-press]");
    this._actions = this.shadowRoot.querySelector(".actions");
    this._knob = this.shadowRoot.querySelector(".knob");
    this._dial = this.shadowRoot.querySelector(".dial");
  }

  connectedCallback() {
    this.#listeners?.abort();
    this.#listeners = new AbortController();
    const options = { signal: this.#listeners.signal };
    this._label.textContent = this.getAttribute("label") || "ROTARY ENCODER";
    this._press.textContent = this.getAttribute("press-label") || "PRESS";
    this._actions.querySelectorAll("[data-direction]").forEach((button) => {
      button.addEventListener("click", () => this.rotate(Number(button.dataset.direction)), options);
    });
    this._press.addEventListener("click", () => this.emit("press"), options);
    this._knob.addEventListener("click", () => this.emit("press"), options);
    this._knob.addEventListener("keydown", (event) => {
      const direction = { ArrowUp: 1, ArrowRight: 1, ArrowDown: -1, ArrowLeft: -1 }[event.key];
      if (!direction || this.disabled) return;
      event.preventDefault();
      this.rotate(direction);
    }, options);
    this._knob.addEventListener("wheel", (event) => {
      if (this.disabled || this.shadowRoot.activeElement !== this._knob || event.ctrlKey || event.metaKey || !event.deltaY) return;
      event.preventDefault();
      const delta = -event.deltaY * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? 160 : 1);
      if (Math.sign(delta) !== Math.sign(this.#wheel)) this.#wheel = 0;
      this.#wheel += delta;
      // Accumulate trackpad deltas; cap each event so a page-sized wheel jump stays manageable.
      const steps = Math.sign(this.#wheel) * Math.min(12, Math.floor(Math.abs(this.#wheel) / 40));
      this.#wheel = steps ? this.#wheel % 40 : this.#wheel;
      for (let step = 0; step < Math.abs(steps); step++) this.rotate(Math.sign(steps));
    }, { ...options, passive: false });
    this._knob.addEventListener("blur", () => { this.#wheel = 0; }, options);
    this.render();
  }

  disconnectedCallback() {
    this.#listeners?.abort();
    this.#wheel = 0;
  }

  attributeChangedCallback() {
    if (!this._label) return;
    this._label.textContent = this.getAttribute("label") || "ROTARY ENCODER";
    this._press.textContent = this.getAttribute("press-label") || "PRESS";
    this.render();
  }

  get disabled() { return this.hasAttribute("disabled"); }
  set disabled(value) { this.toggleAttribute("disabled", Boolean(value)); }
  get stepsPerTurn() {
    const value = Number(this.getAttribute("steps-per-turn"));
    return Number.isInteger(value) && value > 0 && value <= 360 ? value : 24;
  }

  get value() {
    const value = Number(this.getAttribute("value"));
    return Number.isFinite(value) ? value : 0;
  }

  set value(value) {
    const number = Number(value);
    this.setAttribute("value", Number.isFinite(number) ? String(number) : "0");
  }

  render() {
    this._value.textContent = String(this.value);
    this.#angle = this.value * 360 / this.stepsPerTurn;
    this.shadowRoot.querySelector('.scale').style.setProperty('--tick-angle', `${360 / this.stepsPerTurn}deg`);
    this._dial.style.transform = `rotate(${this.#angle}deg)`;
    this.shadowRoot.querySelectorAll("button").forEach(button => { button.disabled = this.disabled; });
    if (this.disabled) this.#wheel = 0;
  }

  rotate(direction) {
    if (this.disabled) return;
    this.#angle += direction * 360 / this.stepsPerTurn;
    this._dial.style.transform = `rotate(${this.#angle}deg)`;
    this.emit("rotate", { direction });
  }

  emit(type, detail = {}) {
    if (this.disabled) return;
    this.dispatchEvent(new CustomEvent("gar-rotary-input", {
      detail: { type, ...detail }, bubbles: true, composed: true,
    }));
  }
}

if (!customElements.get("gar-rotary")) customElements.define("gar-rotary", GarRotary);
