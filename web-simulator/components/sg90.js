import { installComponentStyles } from "./component-styles.mjs";
import {
  channelPulse,
  emptyPca9685State,
  pulseToPreviewAngle,
} from "./servo-model.mjs";

function integerAttribute(element, name, fallback) {
  const value = Number.parseInt(element.getAttribute(name) ?? "", 10);
  return Number.isInteger(value) ? value : fallback;
}

export class GarSg90 extends HTMLElement {
  static observedAttributes = ['controller-id', 'channel', 'min-pulse-us', 'max-pulse-us'];
  #state = emptyPca9685State();
  #controller = null;
  #messageHandler = ({ detail }) => { this.#state = detail; this.render(); };

  constructor() {
    super();
    const root = this.attachShadow({ mode: 'open' });
    root.innerHTML = `
      <article class="hardware-card servo-card" aria-label="SG90 servo motor">
        <header class="component-heading">
          <div><span class="eyebrow">MICRO SERVO</span><h2>SG90</h2></div>
          <output data-state>waiting</output>
        </header>
        <div class="servo-drawing" aria-hidden="true">
          <span class="servo-ear left"></span><span class="servo-ear right"></span>
          <span class="servo-body"><i class="servo-horn"></i></span>
          <span class="servo-wire signal"></span><span class="servo-wire power"></span><span class="servo-wire ground"></span>
        </div>
        <div class="servo-reading">
          <strong data-component-id></strong><span data-route></span>
          <output data-angle>—</output><small data-pulse>signal off</small>
        </div>
      </article>`;
    installComponentStyles(root);
  }

  attributeChangedCallback() {
    if (this.isConnected) this.configure();
  }

  connectedCallback() {
    this.configure();
  }

  configure() {
    this.#controller?.removeEventListener('gar-pca9685-state', this.#messageHandler);
    const componentId = this.id.trim();
    const controllerId = (this.getAttribute("controller-id") ?? "").trim();
    const channel = integerAttribute(this, "channel", -1);
    const controller = this.getRootNode().getElementById(controllerId);
    const valid = componentId
      && controller?.matches("gar-pca9685")
      && channel >= 0
      && channel <= 15;

    const root = this.shadowRoot;
    root.querySelector('[data-state]').textContent = valid ? 'waiting' : 'configuration error';
    root.querySelector('[data-component-id]').textContent = componentId || 'missing id';
    root.querySelector('[data-route]').textContent = controllerId && channel >= 0
      ? `${controllerId} · CH${channel}`
      : 'controller-id/channel required';
    this.toggleAttribute('data-invalid', !valid);

    this.#controller = valid ? controller : null;
    this.#controller?.addEventListener('gar-pca9685-state', this.#messageHandler);
    this.#state = this.#controller?.state ?? emptyPca9685State();
    this.render();
  }

  disconnectedCallback() {
    this.#controller?.removeEventListener('gar-pca9685-state', this.#messageHandler);
    this.#controller = null;
  }

  render() {
    if (!this.isConnected || this.hasAttribute("data-invalid")) return;
    const channelIndex = integerAttribute(this, "channel", -1);
    const channel = this.#state.channels[channelIndex];
    const pulse = channelPulse(channel, this.#state.frequencyHz);
    const minimum = integerAttribute(this, "min-pulse-us", 500);
    const maximum = integerAttribute(this, "max-pulse-us", 2500);
    const angle = pulseToPreviewAngle(pulse.pulseUs, minimum, maximum);

    const root = this.shadowRoot;
    this.classList.toggle('active', pulse.active);
    root.querySelector('[data-state]').textContent = pulse.active ? 'active' : 'stopped';
    if (pulse.active) root.querySelector('.servo-horn').style.transform = `rotate(${angle - 90}deg)`;
    root.querySelector('[data-angle]').textContent = pulse.active ? `${Math.round(angle)}°` : '—';
    root.querySelector('[data-pulse]').textContent = pulse.active
      ? `${Math.round(pulse.pulseUs)} µs`
      : 'signal off';
  }
}

if (!customElements.get('gar-sg90')) customElements.define("gar-sg90", GarSg90);
