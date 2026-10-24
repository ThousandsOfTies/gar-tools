/** Generic connection status indicator. The host supplies an EventTarget source. */
export class GarConnectionStatus extends HTMLElement {
  static observedAttributes = ["label", "connected-label", "disconnected-label"];
  #source = null;
  #connectionHandler = ({ detail }) => this.render(detail);

  constructor() {
    super();
    this.attachShadow({ mode: "open" }).innerHTML = `
      <style>
        :host { display: inline-block; color: var(--gar-status-disconnected, #fbbf24); font: inherit; }
        :host([data-connected="true"]) { color: var(--gar-status-connected, #5eead4); }
      </style>
      <span aria-live="polite"></span>`;
    this._output = this.shadowRoot.querySelector("span");
  }

  get source() { return this.#source; }

  set source(value) {
    this.#source?.removeEventListener("connection", this.#connectionHandler);
    this.#source = value || null;
    if (this.isConnected) this.#source?.addEventListener("connection", this.#connectionHandler);
    this.render({ connected: Boolean(this.#source?.connected) });
  }

  connectedCallback() {
    this.#source?.removeEventListener("connection", this.#connectionHandler);
    this.#source?.addEventListener("connection", this.#connectionHandler);
    this.render({ connected: Boolean(this.#source?.connected) });
  }

  disconnectedCallback() {
    this.#source?.removeEventListener("connection", this.#connectionHandler);
  }

  attributeChangedCallback() {
    if (!this._output) return;
    this.render({ connected: this.dataset.connected === "true" });
  }

  render(detail = {}) {
    const connected = Boolean(detail.connected);
    this.dataset.connected = String(connected);
    this._output.textContent = connected
      ? this.getAttribute("connected-label") || "Connected"
      : this.getAttribute("disconnected-label") || "Disconnected";
  }
}

if (!customElements.get("gar-connection-status")) {
  customElements.define("gar-connection-status", GarConnectionStatus);
}
