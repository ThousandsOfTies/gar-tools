/** Physical StickC Plus2 shell. Application pixels and button meanings are external. */
export class GarStickCPlus2 extends HTMLElement {
  static observedAttributes = ['powered', 'label', 'orientation'];
  constructor() {
    super();
    this.attachShadow({ mode: 'open' }).innerHTML = `
      <style>
        :host{display:block;width:var(--stick-width,480px);max-width:100%;font:12px system-ui;color:#362715}
        .space{position:relative;padding:18px 6px 20px}
        .case{position:relative;aspect-ratio:2 / 1;background:linear-gradient(140deg,#ffce45,#efaa13);border:2px solid #ce870a;border-radius:19px;box-shadow:inset 0 3px 1px #ffdf77,inset 0 -8px 0 #d69214,0 18px 35px #0003}
        .face{position:absolute;left:8%;top:19%;width:54%;box-sizing:border-box;padding:2px;border-radius:2px;background:#080a09;box-shadow:0 0 0 2px #cf8c10,inset 0 0 0 1px #272a24}
        .screen{position:relative;width:100%;aspect-ratio:16 / 9;background:#060807;overflow:hidden}
        ::slotted([slot=display]){display:block;width:100%;height:100%;image-rendering:pixelated;pointer-events:none}
        button{position:absolute;cursor:pointer;touch-action:none;user-select:none;-webkit-user-select:none;color:#714a13;font:700 13px system-ui;border:1px solid #bd800f;box-shadow:inset 0 2px #ffdf65,0 2px 0 #b77b0c;background:#f5b52a}
        button:focus-visible{outline:3px solid #faf7eb;outline-offset:4px}
        button[aria-pressed=true]{filter:brightness(.84);box-shadow:inset 0 2px 4px #8c5a14;transform:translateY(2px)}
        .a{right:9%;top:21%;width:17%;height:58%;border-radius:8px;font-size:28px}
        .a small{display:block;font-size:9px;letter-spacing:.8px;opacity:.65;margin-top:4px}
        .b,.c{height:16px;min-height:16px;width:17%;border-radius:4px;font-size:10px;line-height:12px}
        .b{top:-12px;left:56%}.c{bottom:-10px;right:5%}
        .usb{position:absolute;right:-4px;top:19%;height:18%;width:5px;background:#333b3b;border:2px solid #9a9b8b;border-radius:3px}
        .grove{position:absolute;right:-4px;top:65%;height:17%;width:5px;background:#eee7d6;border:1px solid #bc9a55}
        .pins{position:absolute;left:-4px;top:29%;height:42%;width:4px;background:repeating-linear-gradient(#292c29 0 7px,#b2a075 7px 9px)}
        :host([powered=false]) .screen{filter:brightness(0)}
        :host([orientation=portrait]){width:var(--stick-width,240px)}
        :host([orientation=portrait]) .space{padding:15px 18px}
        :host([orientation=portrait]) .case{aspect-ratio:1 / 2}
        :host([orientation=portrait]) .face{left:19%;top:8%;width:62%}
        :host([orientation=portrait]) .screen{aspect-ratio:9 / 16}
        :host([orientation=portrait]) .a{right:21%;top:auto;bottom:9%;width:58%;height:18%;font-size:32px}
        :host([orientation=portrait]) .b{top:22%;left:auto;right:-13px;width:17px;height:16%}
        :host([orientation=portrait]) .c{bottom:8%;right:auto;left:-13px;width:17px;height:16%}
        :host([orientation=portrait]) .usb{right:25%;top:auto;bottom:-4px;width:23%;height:5px}
        :host([orientation=portrait]) .grove{right:58%;top:auto;bottom:-4px;width:23%;height:5px}
        :host([orientation=portrait]) .pins{left:27%;top:-4px;width:46%;height:4px}
      </style>
      <div class="space"><div class="case" role="group">
        <div class="face"><div class="screen"><slot name="display"></slot></div></div>
        <button class="a" data-key="A" aria-label="Button A" aria-pressed="false">M5<small>A</small></button>
        <button class="b" data-key="B" aria-label="Button B" aria-pressed="false">B</button>
        <button class="c" data-key="C" aria-label="Button C / Power" aria-pressed="false">C</button>
        <i class="pins" title="8-pin expansion"></i><i class="usb" title="USB-C"></i><i class="grove" title="Grove"></i>
      </div></div>`;
    this.contacts = new Map();
  }
  get powered() { return this.getAttribute('powered') !== 'false'; }
  set powered(value) { this.setAttribute('powered', String(Boolean(value))); }
  connectedCallback() {
    this.listeners?.abort();
    this.listeners = new AbortController();
    const options = { signal: this.listeners.signal };
    for (const button of this.shadowRoot.querySelectorAll('button')) {
      const key = button.dataset.key;
      button.addEventListener('pointerdown', event => {
        if (event.button !== 0 || !event.isPrimary) return;
        event.preventDefault(); button.focus(); button.setPointerCapture(event.pointerId);
        this.press(key, `pointer:${event.pointerId}`);
      }, options);
      button.addEventListener('pointerup', event => this.release(key, `pointer:${event.pointerId}`), options);
      for (const name of ['pointercancel', 'lostpointercapture'])
        button.addEventListener(name, event => this.release(key, `pointer:${event.pointerId}`, true), options);
      button.addEventListener('keydown', event => {
        if (![' ', 'Enter'].includes(event.key)) return;
        event.preventDefault();
        if (!event.repeat) this.press(key, `key:${event.key}`);
      }, options);
      button.addEventListener('keyup', event => {
        if (![' ', 'Enter'].includes(event.key)) return;
        event.preventDefault(); this.release(key, `key:${event.key}`);
      }, options);
      button.addEventListener('blur', () => this.cancel(key), options);
    }
    // Letter shortcuts are scoped to the device, never to the whole page.
    this.addEventListener('keydown', event => {
      const key = event.key.toUpperCase();
      if (!['A','B','C'].includes(key) || event.ctrlKey || event.altKey || event.metaKey) return;
      event.preventDefault(); if (!event.repeat) this.press(key, `letter:${key}`);
    }, options);
    this.addEventListener('keyup', event => {
      const key = event.key.toUpperCase();
      if (['A','B','C'].includes(key)) { event.preventDefault(); this.release(key, `letter:${key}`); }
    }, options);
    this.addEventListener('focusout', event => {
      if (!this.contains(event.relatedTarget) && !this.shadowRoot.contains(event.relatedTarget)) this.cancelAll();
    }, options);
    window.addEventListener('blur', () => this.cancelAll(), options);
    document.addEventListener('visibilitychange', () => { if (document.hidden) this.cancelAll(); }, options);
    this.attributeChangedCallback();
  }
  disconnectedCallback() { this.cancelAll(); this.listeners?.abort(); }
  attributeChangedCallback(name) {
    if (name === 'powered') this.cancelAll();
    this.shadowRoot.querySelector('.case').setAttribute('aria-label', this.getAttribute('label') || 'M5StickC Plus2');
  }
  press(button, source) {
    if (this.contacts.has(button) || (!this.powered && button !== 'C')) return;
    this.contacts.set(button, { source, at: performance.now() });
    this.shadowRoot.querySelector(`[data-key=${button}]`).setAttribute('aria-pressed', 'true');
    this.emit(button, 'down', 0);
  }
  release(button, source, cancelled = false) {
    const contact = this.contacts.get(button);
    if (!contact || contact.source !== source) return;
    this.contacts.delete(button);
    this.shadowRoot.querySelector(`[data-key=${button}]`).setAttribute('aria-pressed', 'false');
    this.emit(button, cancelled ? 'cancel' : 'up', Math.round(performance.now() - contact.at));
  }
  cancel(button) {
    const contact = this.contacts.get(button);
    if (contact) this.release(button, contact.source, true);
  }
  cancelAll() { for (const button of [...this.contacts.keys()]) this.cancel(button); }
  emit(button, phase, durationMs) {
    this.dispatchEvent(new CustomEvent('gar-button', { detail: { button, phase, durationMs }, bubbles: true, composed: true }));
  }
}
if (!customElements.get('gar-stickc-plus2')) customElements.define('gar-stickc-plus2', GarStickCPlus2);
