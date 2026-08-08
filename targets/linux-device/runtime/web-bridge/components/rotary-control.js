import { bridgeClient } from "./bridge-client.js";

class GarRotaryControl extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `<section><span class="label">ROTARY ENCODER</span><output>0</output><div><button data-direction="-1">−</button><button data-direction="1">+</button><button data-press>PRESS</button></div></section>`;
    this.querySelectorAll("[data-direction]").forEach((button) => button.addEventListener("click", () =>
      bridgeClient.send({ type: "rotary_rotate", direction: Number(button.dataset.direction) })));
    this.querySelector("[data-press]").addEventListener("click", () => bridgeClient.send({ type: "rotary_press" }));
    bridgeClient.addEventListener("message", ({ detail }) => this.update(detail));
    if (bridgeClient.state) this.update({ type: "init", state: bridgeClient.state });
  }
  update(message) {
    const count = message.type === "init" ? message.state?.gpio?.rotary?.counter : message.type === "rotary" ? message.counter : null;
    if (count !== null && count !== undefined) this.querySelector("output").value = String(count);
  }
}
customElements.define("gar-rotary-control", GarRotaryControl);
