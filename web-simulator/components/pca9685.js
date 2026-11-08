import { installComponentStyles } from "./component-styles.mjs";
import {
  channelPulse,
  emptyPca9685State,
  pca9685StateFromMessage,
} from "./servo-model.mjs";

export class GarPca9685 extends HTMLElement {
  static observedAttributes = ['device', 'address'];
  #state = emptyPca9685State();
  #transport = null;
  #messageHandler = ({ detail }) => this.update(detail);

  constructor() {
    super();
    const root = this.attachShadow({ mode: 'open' });
    root.innerHTML = `
      <section class="hardware-card pca-board" aria-label="PCA9685 servo controller">
        <header class="component-heading">
          <div><span class="eyebrow">PWM CONTROLLER · 1 BOARD</span><h2>PCA9685</h2></div>
          <output data-address>0x40</output>
        </header>
        <div class="board-visual" aria-hidden="true">
          <span class="terminal terminal-power">V+</span>
          <span class="chip">PCA<br>9685</span>
          <span class="terminal terminal-i2c">I²C</span>
          <div class="channel-pins"></div>
        </div>
        <div class="component-stats">
          <span>Device <output data-device></output></span>
          <span>Frequency <output data-frequency>waiting</output></span>
          <span>Active <output data-active>0 / 16</output></span>
        </div>
        <ol class="channel-list" aria-label="PWM channel states"></ol>
      </section>`;
    installComponentStyles(root);
    const pins = root.querySelector('.channel-pins');
    const list = root.querySelector('.channel-list');
    for (let channel = 0; channel < 16; channel += 1) {
      const pin = document.createElement('i');
      pin.dataset.channel = String(channel);
      pins.append(pin);
      const item = document.createElement('li');
      item.innerHTML = `<span>CH${channel}</span><meter min="0" max="4096" value="0"></meter><output>off</output>`;
      list.append(item);
    }
  }

  get state() { return this.#state; }
  get transport() { return this.#transport; }
  set transport(value) {
    this.#transport?.removeEventListener('message', this.#messageHandler);
    this.#transport = value;
    if (this.isConnected) this.subscribe();
  }

  subscribe() {
    this.#transport?.removeEventListener('message', this.#messageHandler);
    this.#transport?.addEventListener('message', this.#messageHandler);
    this.update({ type: 'init', state: this.#transport?.state ?? null });
  }

  attributeChangedCallback() {
    if (this.isConnected) {
      this.shadowRoot.querySelector('[data-device]').textContent = this.getAttribute('device') || 'unbound';
      this.subscribe();
    }
  }

  connectedCallback() {
    this.shadowRoot.querySelector('[data-device]').textContent = this.getAttribute('device') || 'unbound';
    this.subscribe();
  }

  disconnectedCallback() {
    this.#transport?.removeEventListener("message", this.#messageHandler);
    this.update({ type: 'init', state: null });
  }

  update(message) {
    this.#state = pca9685StateFromMessage(message, this.#state, {
      device: this.getAttribute('device'),
      address: this.hasAttribute('address') ? Number(this.getAttribute('address')) : undefined,
    });
    this.render();
    this.dispatchEvent(new CustomEvent('gar-pca9685-state', { detail: this.#state }));
  }

  render() {
    if (!this.isConnected) return;
    const frequency = this.#state.frequencyHz;
    const root = this.shadowRoot;
    root.querySelector('[data-address]').textContent = `0x${this.#state.address.toString(16).padStart(2, '0').toUpperCase()}`;
    root.querySelector('[data-frequency]').textContent = frequency ? `${frequency.toFixed(1)} Hz` : 'waiting';

    let activeCount = 0;
    this.#state.channels.forEach((channel, index) => {
      const pulse = channelPulse(channel, frequency);
      if (pulse.active) activeCount += 1;
      const pin = root.querySelector(`.channel-pins [data-channel="${index}"]`);
      pin.classList.toggle('active', pulse.active);
      const row = root.querySelector(`.channel-list li:nth-child(${index + 1})`);
      row.classList.toggle('active', pulse.active);
      row.querySelector('meter').value = pulse.counts;
      row.querySelector('output').textContent = pulse.active ? `${Math.round(pulse.pulseUs)} µs` : 'off';
    });
    root.querySelector('[data-active]').textContent = `${activeCount} / 16`;
  }
}

if (!customElements.get('gar-pca9685')) customElements.define("gar-pca9685", GarPca9685);
