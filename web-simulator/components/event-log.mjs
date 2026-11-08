/** Bounded, text-only event history, independent of event format and transport. */
export class GarEventLog extends HTMLElement {
  static observedAttributes = ["max-entries", "label", "clear-label", "empty-label"];

  constructor() {
    super();
    this.attachShadow({ mode: "open" }).innerHTML = `
      <style>
        :host{display:block;color:inherit;font:inherit}
        *{box-sizing:border-box}
        section{padding:16px;border:1px solid var(--gar-border,#cbd5e1);border-radius:12px;background:var(--gar-panel,#fff)}
        header{display:flex;align-items:center;gap:10px;margin-bottom:12px}
        h2{font-family:inherit;font-size:1em;font-weight:650;margin:0;flex:1}
        output{font-size:.8em;font-variant-numeric:tabular-nums}
        button{font:inherit;color:inherit;background:var(--gar-panel,#fff);border:1px solid var(--gar-border,#cbd5e1);border-radius:7px;padding:5px 9px;cursor:pointer}
        button:disabled{opacity:.5;cursor:default}
        button:focus-visible{outline:2px solid var(--gar-accent,#2563eb);outline-offset:3px}
        .history{max-height:var(--gar-log-height,260px);overflow:auto}
        ol{display:grid;gap:7px;list-style:none;padding:0;margin:0;font:12px/1.5 ui-monospace,monospace;overflow-wrap:anywhere;white-space:pre-wrap}
        li+li{border-top:1px solid var(--gar-border,#cbd5e1);padding-top:7px}
        p{margin:0;font-size:.85em;opacity:.7}[hidden]{display:none!important}
      </style>
      <section><header><h2 id="label"></h2><output aria-hidden="true">0</output><button type="button"></button></header>
      <div class="history" role="log" aria-labelledby="label" aria-live="polite" aria-relevant="additions"><ol></ol></div>
      <p></p></section>`;
    this._list = this.shadowRoot.querySelector("ol");
    this._history = this.shadowRoot.querySelector(".history");
    this._button = this.shadowRoot.querySelector("button");
    this._button.addEventListener("click", () => this.clear());
    this._sync();
  }

  connectedCallback() {
    for (const name of ["maxEntries", "label", "clearLabel", "emptyLabel"]) {
      if (!Object.hasOwn(this, name)) continue;
      const value = this[name];
      delete this[name];
      this[name] = value;
    }
    this._sync();
  }

  attributeChangedCallback() { this._sync(); }

  get maxEntries() {
    const value = Number(this.getAttribute("max-entries") ?? 200);
    return Number.isFinite(value) && value >= 1 ? Math.floor(value) : 200;
  }
  set maxEntries(value) { this.setAttribute("max-entries", String(value)); }
  get label() { return this.getAttribute("label") ?? "Events"; }
  set label(value) { this.setAttribute("label", String(value)); }
  get clearLabel() { return this.getAttribute("clear-label") ?? "Clear"; }
  set clearLabel(value) { this.setAttribute("clear-label", String(value)); }
  get emptyLabel() { return this.getAttribute("empty-label") ?? "No events yet"; }
  set emptyLabel(value) { this.setAttribute("empty-label", String(value)); }
  get count() { return this._list.childElementCount; }

  append(text) {
    const entry = document.createElement("li");
    entry.textContent = String(text);
    const atEnd = this._history.scrollHeight - this._history.scrollTop - this._history.clientHeight < 4;
    this._list.append(entry);
    this._sync();
    if (atEnd) this._history.scrollTop = this._history.scrollHeight;
  }

  clear() {
    this._list.replaceChildren();
    this._sync();
  }

  _sync() {
    if (!this._list) return;
    while (this.count > this.maxEntries) this._list.firstElementChild.remove();
    this.shadowRoot.querySelector("h2").textContent = this.label;
    this._button.textContent = this.clearLabel;
    this._button.disabled = this.count === 0;
    this.shadowRoot.querySelector("output").textContent = String(this.count);
    const empty = this.shadowRoot.querySelector("p");
    empty.textContent = this.emptyLabel;
    empty.hidden = this.count !== 0;
  }
}

if (!customElements.get("gar-event-log")) customElements.define("gar-event-log", GarEventLog);
