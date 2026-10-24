import { decodeRgb565 } from './framebuffer.mjs';

/** A board-independent pixel display. Application rendering and gestures are external. */
export class GarDisplay extends HTMLElement {
  static observedAttributes = ['width', 'height', 'brightness', 'powered', 'label'];
  constructor() {
    super();
    this.attachShadow({ mode: 'open' }).innerHTML = `
      <style>
        :host{display:block;width:320px;max-width:100%;background:#101820}
        canvas{display:block;width:100%;height:auto;touch-action:none;image-rendering:pixelated}
        canvas:focus-visible{outline:3px solid #519de5;outline-offset:3px}
      </style><canvas tabindex="0" role="img"></canvas>`;
    this.canvas = this.shadowRoot.querySelector('canvas');
    this.contact = null;
  }
  connectedCallback() {
    this.listeners?.abort();
    this.listeners = new AbortController();
    const options = { signal: this.listeners.signal };
    this.canvas.addEventListener('pointerdown', event => {
      if (event.button !== 0 || this.contact || !this.powered) return;
      event.preventDefault();
      this.canvas.focus({ preventScroll: true });
      this.canvas.setPointerCapture(event.pointerId);
      this.start(event.pointerId, this.point(event));
    }, options);
    this.canvas.addEventListener('pointermove', event => {
      if (this.contact?.id !== event.pointerId) return;
      this.contact.point = this.point(event);
      this.emit('move', this.contact.point);
    }, options);
    this.canvas.addEventListener('pointerup', event => {
      if (this.contact?.id === event.pointerId) this.finish(false, this.point(event));
    }, options);
    for (const type of ['pointercancel', 'lostpointercapture'])
      this.canvas.addEventListener(type, event => {
        if (this.contact?.id === event.pointerId) this.finish(true);
      }, options);
    this.canvas.addEventListener('keydown', event => {
      if (![' ', 'Enter'].includes(event.key)) return;
      event.preventDefault();
      if (this.powered && !event.repeat && !this.contact)
        this.start('keyboard', { x: Math.floor(this.width / 2), y: Math.floor(this.height / 2) });
    }, options);
    this.canvas.addEventListener('keyup', event => {
      if (![' ', 'Enter'].includes(event.key)) return;
      event.preventDefault();
      if (this.contact?.id === 'keyboard') this.finish(false);
    }, options);
    this.canvas.addEventListener('blur', () => this.finish(true), options);
    window.addEventListener('blur', () => this.finish(true), options);
    this.sync();
  }
  disconnectedCallback() { this.finish(true); this.listeners?.abort(); }
  attributeChangedCallback() { this.sync(); }
  dimension(name, fallback) {
    const value = Number(this.getAttribute(name));
    return Number.isInteger(value) && value > 0 && value <= 4096 ? value : fallback;
  }
  get width() { return this.dimension('width', 320); }
  set width(value) { this.setAttribute('width', value); }
  get height() { return this.dimension('height', 240); }
  set height(value) { this.setAttribute('height', value); }
  get powered() { return this.getAttribute('powered') !== 'false'; }
  set powered(value) { this.setAttribute('powered', Boolean(value)); }
  get brightness() {
    const value = Number(this.getAttribute('brightness') ?? 100);
    return Number.isFinite(value) ? Math.max(0, Math.min(100, value)) : 100;
  }
  set brightness(value) { this.setAttribute('brightness', value); }
  get displayContext() { return this.canvas.getContext('2d'); }
  sync() {
    if (!this.canvas) return;
    if (!this.powered || this.canvas.width !== this.width || this.canvas.height !== this.height)
      this.finish(true);
    if (this.canvas.width !== this.width) this.canvas.width = this.width;
    if (this.canvas.height !== this.height) this.canvas.height = this.height;
    this.canvas.style.opacity = this.powered ? this.brightness / 100 : 0;
    this.canvas.tabIndex = this.powered ? 0 : -1;
    this.canvas.setAttribute('aria-disabled', String(!this.powered));
    this.canvas.setAttribute('aria-label', this.getAttribute('label') || `${this.width} × ${this.height} display`);
  }
  writeFrame(bytes, { littleEndian = false } = {}) {
    this.displayContext.putImageData(new ImageData(decodeRgb565(bytes, {
      width: this.width, height: this.height, littleEndian,
    }), this.width, this.height), 0, 0);
  }
  point(event) {
    const rect = this.canvas.getBoundingClientRect();
    return {
      x: Math.max(0, Math.min(this.width - 1, Math.floor((event.clientX - rect.left) * this.width / rect.width))),
      y: Math.max(0, Math.min(this.height - 1, Math.floor((event.clientY - rect.top) * this.height / rect.height))),
    };
  }
  start(id, point) {
    this.contact = { id, point, at: performance.now() };
    this.emit('start', point);
  }
  finish(cancelled, point = this.contact?.point) {
    const contact = this.contact;
    if (!contact) return;
    this.contact = null;
    if (typeof contact.id === 'number' && this.canvas.hasPointerCapture(contact.id))
      this.canvas.releasePointerCapture(contact.id);
    this.emit(cancelled ? 'cancel' : 'end', { ...point, durationMs: Math.round(performance.now() - contact.at) });
  }
  emit(phase, point) {
    this.dispatchEvent(new CustomEvent('gar-touch', { detail: { phase, ...point }, bubbles: true, composed: true }));
  }
}
if (!customElements.get('gar-display')) customElements.define('gar-display', GarDisplay);
