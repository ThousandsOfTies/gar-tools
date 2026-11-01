/** Schema-driven simulator inputs. Contains no device, transport, or app state. */
export class GarSimControls extends HTMLElement {
  static observedAttributes = ["disabled", "label"];

  constructor() {
    super();
    this._schema = [];
    this._inputs = new Map();
    this.attachShadow({ mode: "open" }).innerHTML = `
      <style>
        :host{display:block;color:inherit;font:inherit}
        *{box-sizing:border-box}
        fieldset{min-width:0;margin:0;padding:16px;border:1px solid var(--gar-border,#cbd5e1);border-radius:12px;background:var(--gar-panel,#fff)}
        legend{padding:0 6px;font-weight:650}
        .fields{display:grid;gap:14px}
        label{display:grid;gap:6px;font-size:.9em}
        .caption{display:flex;justify-content:space-between;gap:12px}
        .checkbox{display:flex;align-items:center;gap:9px}
        input,select,button{font:inherit;accent-color:var(--gar-accent,#2563eb)}
        input[type=range]{width:100%;margin:0}
        select,button{padding:8px 10px;border:1px solid var(--gar-border,#cbd5e1);border-radius:7px;background:var(--gar-panel,#fff);color:inherit}
        button{cursor:pointer;text-align:left}button:disabled{cursor:default}
        :disabled{opacity:.6}fieldset:disabled{opacity:1}
        :focus-visible{outline:2px solid var(--gar-accent,#2563eb);outline-offset:3px}
        .value{font-variant-numeric:tabular-nums;white-space:nowrap}
      </style>
      <fieldset><legend></legend><div class="fields"></div></fieldset>`;
    this._fieldset = this.shadowRoot.querySelector("fieldset");
    this._fields = this.shadowRoot.querySelector(".fields");
    // Install once on the persistent shadow root: reconnecting cannot duplicate events.
    for (const type of ["input", "change", "click"]) {
      this.shadowRoot.addEventListener(type, (event) => this._handleInput(event));
    }
    this._syncAttributes();
  }

  connectedCallback() {
    // Honor properties assigned before the custom element module was loaded.
    for (const name of ["schema", "values", "disabled", "label"]) {
      if (!Object.hasOwn(this, name)) continue;
      const value = this[name];
      delete this[name];
      this[name] = value;
    }
    this._syncAttributes();
  }

  attributeChangedCallback() { this._syncAttributes(); }

  get label() { return this.getAttribute("label") ?? "Controls"; }
  set label(value) { this.setAttribute("label", String(value)); }
  get disabled() { return this.hasAttribute("disabled"); }
  set disabled(value) { this.toggleAttribute("disabled", Boolean(value)); }

  get schema() {
    return this._schema.map((item) => ({
      ...item,
      ...(item.options ? { options: item.options.map((option) => ({ ...option })) } : {}),
    }));
  }

  set schema(schema) {
    if (!Array.isArray(schema)) throw new TypeError("schema must be an array");
    const ids = new Set();
    const items = schema.map((item) => {
      if (!item || typeof item.id !== "string" || !item.id || ids.has(item.id)) {
        throw new TypeError("Each control needs a unique non-empty string id");
      }
      if (!["range", "checkbox", "select", "action"].includes(item.type)) {
        throw new TypeError(`Unsupported control type: ${item.type}`);
      }
      ids.add(item.id);
      const result = { ...item };
      if (item.type === "select") {
        if (!Array.isArray(item.options)) throw new TypeError("select options must be an array");
        result.options = item.options.map((option) => typeof option === "object" && option !== null
          ? { value: String(option.value), label: String(option.label ?? option.value) }
          : { value: String(option), label: String(option) });
      }
      return result;
    });
    this._schema = items;
    this._inputs.clear();
    this._fields.replaceChildren();
    for (const item of items) this._createControl(item);
  }

  get values() {
    return Object.fromEntries([...this._inputs].filter(([, field]) => field.item.type !== "action")
      .map(([id, field]) => [id, this._value(field)]));
  }

  /** Merge known value controls; actions have no persistent state. Never emits. */
  set values(values) {
    if (!values || typeof values !== "object" || Array.isArray(values)) {
      throw new TypeError("values must be an object keyed by control id");
    }
    for (const [id, value] of Object.entries(values)) {
      const field = this._inputs.get(id);
      if (!field || field.item.type === "action") continue;
      if (field.item.type === "checkbox") field.input.checked = Boolean(value);
      else field.input.value = String(value);
      this._syncOutput(field);
    }
  }

  _syncAttributes() {
    if (!this._fieldset) return;
    this._fieldset.disabled = this.disabled;
    this.shadowRoot.querySelector("legend").textContent = this.label;
  }

  _createControl(item) {
    const input = document.createElement(item.type === "action" ? "button" : item.type === "select" ? "select" : "input");
    input.dataset.controlId = item.id;
    input.disabled = Boolean(item.disabled);
    const field = { input, item };
    this._inputs.set(item.id, field);
    if (item.type === "action") {
      input.type = "button";
      input.textContent = String(item.label ?? item.id);
      this._fields.append(input);
      return;
    }
    const label = document.createElement("label");
    input.id = `control-${this._inputs.size}`;
    label.htmlFor = input.id;
    const caption = document.createElement("span");
    caption.className = "caption";
    const text = document.createElement("span");
    text.textContent = String(item.label ?? item.id);
    caption.append(text);
    if (item.type === "checkbox") {
      label.className = "checkbox";
      input.type = "checkbox";
      input.checked = Boolean(item.value);
      label.append(input, caption);
    } else {
      if (item.type === "range") {
        input.type = "range";
        for (const key of ["min", "max", "step"]) {
          if (item[key] !== undefined) input.setAttribute(key, String(item[key]));
        }
        input.value = String(item.value ?? item.min ?? 0);
        // An <output> is labelable and would steal this label from the range.
        // The native input exposes the current value via aria-valuetext below.
        field.output = document.createElement("span");
        field.output.className = "value";
        field.output.setAttribute("aria-hidden", "true");
        caption.append(field.output);
      } else {
        for (const option of item.options) {
          const element = document.createElement("option");
          element.value = option.value;
          element.textContent = option.label;
          input.append(element);
        }
        if (item.value !== undefined) input.value = String(item.value);
      }
      label.append(caption, input);
    }
    this._syncOutput(field);
    this._fields.append(label);
  }

  _value({ input, item }) {
    if (item.type === "range") return input.valueAsNumber;
    if (item.type === "checkbox") return input.checked;
    if (item.type === "action") return item.value ?? true;
    return input.value;
  }

  _syncOutput(field) {
    if (!field.output) return;
    const text = `${field.input.value}${field.item.unit ?? ""}`;
    field.output.textContent = text;
    field.input.setAttribute("aria-valuetext", text);
  }

  _handleInput(event) {
    const input = event.target;
    const field = this._inputs.get(input?.dataset?.controlId);
    if (!field || field.input !== input || this.disabled || input.disabled) return;
    const expected = field.item.type === "action" ? "click" : field.item.type === "range" ? "input" : "change";
    if (event.type !== expected) return;
    this._syncOutput(field);
    this.dispatchEvent(new CustomEvent("gar-control", {
      bubbles: true, composed: true,
      detail: { id: field.item.id, value: this._value(field) },
    }));
  }
}

if (!customElements.get("gar-sim-controls")) customElements.define("gar-sim-controls", GarSimControls);
