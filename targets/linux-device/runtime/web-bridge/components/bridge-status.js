import { bridgeClient } from "./bridge-client.js";

class GarBridgeStatus extends HTMLElement {
  connectedCallback() {
    this.render(false);
    bridgeClient.addEventListener("connection", ({ detail }) => this.render(detail.connected));
  }
  render(connected) {
    this.textContent = connected ? "● Bridge connected" : "● Bridge reconnecting";
    this.dataset.connected = String(connected);
  }
}
customElements.define("gar-bridge-status", GarBridgeStatus);
