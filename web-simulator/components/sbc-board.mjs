/** Generic single-board computer appearance. No transport or Product behavior. */
export class GarSbcBoard extends HTMLElement {
  static observedAttributes = ['label', 'soc', 'memory', 'architecture', 'powered', 'readonly'];
  constructor() {
    super();
    this.attachShadow({mode:'open'}).innerHTML = `
      <style>
        :host{display:block;max-width:100%;font:12px/1.5 system-ui,sans-serif;color:var(--gar-component-text,#263b3b)}
        *{box-sizing:border-box}.board{position:relative;min-height:145px;max-width:340px;padding:30px 22px 35px;border:2px solid #315c42;border-radius:12px;background:linear-gradient(135deg,#4a7a54,#28553c);color:#e4ebd1;box-shadow:inset 0 0 0 2px #739165;display:flex;align-items:center;justify-content:space-between;gap:12px}
        .board:before,.board:after{content:'';position:absolute;top:8px;width:11px;height:11px;border-radius:50%;border:3px solid #c5b070;background:var(--gar-component-panel,#f8f8f2)}.board:before{left:9px}.board:after{right:9px}
        .label{font-size:11px;max-width:95px;overflow-wrap:anywhere}.soc{background:#25312a;box-shadow:0 0 0 3px #94a18b66;border:2px solid #738371;min-width:62px;min-height:55px;padding:8px 4px;text-align:center;display:grid;place-content:center;font:10px/1.5 ui-monospace,monospace}.memory{font:9px/1.5 ui-monospace,monospace;background:#263b2c;padding:9px 5px;text-align:center}
        .pins{position:absolute;left:22px;right:22px;bottom:12px;border-top:5px dotted #c8b771;text-align:center;font:7px ui-monospace,monospace;padding-top:4px}.ports{display:flex;gap:13px;padding:0 16px;flex-wrap:wrap;margin-top:-4px;position:relative}.port{background:#d3dad2;border:1px solid #9daaa0;border-radius:0 0 5px 5px;padding:5px 9px;font:9px ui-monospace,monospace;color:#34453c}.led{position:absolute;right:10px;bottom:32px;width:5px;height:5px;border-radius:1px;background:#dca345}.off .led{background:#7d8277}.off{filter:saturate(.35)}
        footer{display:flex;align-items:center;justify-content:space-between;gap:10px;max-width:340px;margin-top:10px;color:var(--gar-component-muted,#627166);font-size:10px}button{font:inherit;color:inherit;border:1px solid var(--gar-component-border,#c8d2c4);border-radius:5px;background:var(--gar-component-panel,#f5f6ef);padding:5px 9px;cursor:pointer}button:focus-visible{outline:2px solid #447c61;outline-offset:2px}.note{font-size:9px;max-width:340px;color:var(--gar-component-muted,#627166);margin:8px 0 0}
      </style>
      <div class="board" role="img"><span class="label"></span><span class="soc"></span><span class="memory"></span><span class="pins">GPIO / I²C / SPI</span><span class="led"></span></div>
      <div class="ports"></div><footer><span class="architecture"></span><button type="button"></button></footer><p class="note">部品を表す模式図です。実際の端子配置・配線図ではありません。</p>`;
    this._ports = ['USB', 'USB'];
    this.shadowRoot.querySelector('button').addEventListener('click', () => {
      this.powered = !this.powered;
      this.dispatchEvent(new CustomEvent('gar-board-power', {detail:{powered:this.powered},bubbles:true,composed:true}));
    });
  }
  connectedCallback() { this.sync(); }
  attributeChangedCallback() { this.sync(); }
  get powered() { return this.getAttribute('powered') !== 'false'; }
  set powered(value) { this.setAttribute('powered',String(Boolean(value))); }
  get ports() { return [...this._ports]; }
  set ports(value) {
    if (!Array.isArray(value) || value.length > 8 || value.some(x => typeof x !== 'string' || x.length > 32)) throw new TypeError('ports must be up to eight short labels');
    this._ports = [...value]; this.sync();
  }
  sync() {
    if (!this.shadowRoot) return;
    const root = this.shadowRoot, label = this.getAttribute('label') || 'Single-board computer';
    for (const name of ['label','soc','memory','architecture']) root.querySelector('.'+name).textContent = name === 'label' ? label : this.getAttribute(name) || name.toUpperCase();
    const board = root.querySelector('.board'); board.classList.toggle('off',!this.powered); board.setAttribute('aria-label',`${label}, ${this.getAttribute('soc')||'SoC'}, ${this.powered?'電源入':'電源切'}`);
    const button = root.querySelector('button'); button.disabled = this.hasAttribute('readonly'); button.textContent = button.disabled ? '基板モデル表示' : this.powered ? '電源を切る' : '電源を入れる'; button.setAttribute('aria-pressed', String(this.powered));
    const ports = root.querySelector('.ports'); ports.replaceChildren(...this._ports.map(label => { const span = document.createElement('span'); span.className='port'; span.textContent=label; return span; }));
  }
}
if (!customElements.get('gar-sbc-board')) customElements.define('gar-sbc-board',GarSbcBoard);
