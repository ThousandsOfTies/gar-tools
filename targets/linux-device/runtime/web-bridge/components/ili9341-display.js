import { bridgeClient } from "./bridge-client.js";

class GarIli9341Display extends HTMLElement {
  connectedCallback() {
    this.innerHTML = `<section><span class="label">ILI9341 DISPLAY</span><canvas width="320" height="240" aria-label="Simulated display"></canvas></section>`;
    bridgeClient.addEventListener("message", ({ detail }) => this.update(detail));
    if (bridgeClient.state) this.update({ type: "init", state: bridgeClient.state });
  }
  update(message) {
    const display = message.type === "init" ? message.state?.spi?.ili9341 : message.type === "ili9341" ? message : null;
    if (!display?.pixels) return;
    const width = Number(display.width) || 320;
    const height = Number(display.height) || 240;
    const bytes = Uint8Array.from(atob(display.pixels), (char) => char.charCodeAt(0));
    if (bytes.length < width * height * 2) return;
    const canvas = this.querySelector("canvas");
    canvas.width = width; canvas.height = height;
    const image = canvas.getContext("2d").createImageData(width, height);
    for (let pixel = 0; pixel < width * height; pixel += 1) {
      const rgb565 = (bytes[pixel * 2] << 8) | bytes[pixel * 2 + 1];
      const offset = pixel * 4;
      image.data[offset] = ((rgb565 >> 11) & 31) << 3;
      image.data[offset + 1] = ((rgb565 >> 5) & 63) << 2;
      image.data[offset + 2] = (rgb565 & 31) << 3;
      image.data[offset + 3] = 255;
    }
    canvas.getContext("2d").putImageData(image, 0, 0);
  }
}
customElements.define("gar-ili9341-display", GarIli9341Display);
