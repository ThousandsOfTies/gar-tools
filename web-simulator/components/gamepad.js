import { GamepadReader, stick } from './gamepad-model.mjs';

/** Portable input component. Emits gar-gamepad-input; never sends network commands. */
export class GarGamepad extends HTMLElement {
  static observedAttributes = ['disabled', 'button-a-label', 'button-b-label', 'button-x-label', 'button-y-label'];
  reader = new GamepadReader();
  keys = new Set();
  pointer = null;
  physical = false;
  padId = null;
  raf = null;
  connectedCallback() {
    const root = this.shadowRoot || this.attachShadow({ mode: 'open' });
    this.physical = false; this.padId = null; this.reader.reset();
    root.innerHTML = `
      <style>
        :host{display:block;color:#edf1ef;font-family:inherit}*{box-sizing:border-box}
        section{border:1px solid #394739;border-radius:16px;padding:22px;background:linear-gradient(115deg,#222d24,#161e1b)}
        header{display:flex;justify-content:space-between;gap:16px;align-items:center}h2{font-size:20px;margin:4px 0;font-weight:500}small{font:11px ui-monospace,monospace;letter-spacing:2px;color:#d4fc79}
        .status{font-size:12px;color:#acbda6;max-width:45%;overflow-wrap:anywhere}fieldset{border:0;padding:0;margin:0;min-width:0}
        .surface{display:flex;align-items:center;justify-content:space-evenly;gap:28px;padding:24px 0}
        .stick{position:relative;width:154px;height:154px;flex:none;border-radius:50%;border:1px solid #71845d;background:repeating-radial-gradient(circle,#d4fc7906 0 24px,#d4fc791a 25px 26px);touch-action:none;cursor:grab;outline-offset:5px}
        .stick::before,.stick::after{content:'';position:absolute;background:#82966445}.stick::before{width:1px;height:100%;left:50%}.stick::after{height:1px;width:100%;top:50%}
        .knob{position:absolute;width:54px;height:54px;left:49px;top:49px;background:radial-gradient(circle at 35% 30%,#d1e9a3,#789954);border:2px solid #bed58c;border-radius:50%;box-shadow:0 8px 16px #0006;z-index:1;pointer-events:none}
        .readout{text-align:center;font:12px ui-monospace,monospace;margin-top:14px;color:#c2d2b5}.buttons{display:grid;grid-template-columns:repeat(3,62px);grid-template-rows:repeat(3,48px);gap:8px}
        button{font:inherit;border:1px solid #5c7050;border-radius:12px;background:#293727;color:#d4fc79;cursor:pointer;min-height:44px}button:hover{background:#3b4b31}button:focus-visible,.stick:focus-visible,input:focus-visible{outline:2px solid #d4fc79;outline-offset:4px}
        button span{font-size:18px;font-weight:650}button em{display:block;font-size:10px;font-style:normal;color:#d1dcc7;margin-top:2px}
        [data-button=y]{grid-column:2;grid-row:1}[data-button=x]{grid-column:1;grid-row:2}[data-button=b]{grid-column:3;grid-row:2}[data-button=a]{grid-column:2;grid-row:3}
        .footer{display:flex;justify-content:space-between;align-items:center;gap:16px;border-top:1px solid #394739;padding-top:15px;font-size:13px}.footer label{display:flex;align-items:center;gap:8px;cursor:pointer}input{accent-color:#d4fc79;width:18px;height:18px}
        p{font-size:12px;line-height:1.8;color:#a7b79d;margin:13px 0 0}:host([disabled]) fieldset{opacity:.45}fieldset:disabled .stick,button:disabled{cursor:not-allowed}
        @media(max-width:500px){section{padding:16px}.surface{gap:12px}.stick{width:126px;height:126px}.knob{left:35px;top:35px}.buttons{grid-template-columns:repeat(3,48px);grid-template-rows:repeat(3,45px);gap:5px}.footer{align-items:start;flex-direction:column}.status{max-width:50%;font-size:11px}}
      </style>
      <section aria-label="ゲームパッド">
        <header><div><small>GAMEPAD INPUT</small><h2>ゲームパッド</h2></div><span class="status" role="status">画面で操作できます</span></header>
        <fieldset><legend hidden>ゲームパッド入力</legend>
          <div class="surface"><div><div class="stick" tabindex="0" role="group" aria-label="仮想スティック。ドラッグまたは矢印キーで操作、離すと中央に戻る"><div class="knob"></div></div><div class="readout">X +0.00 / Y +0.00</div></div>
          <div class="buttons"><button type="button" data-button="y" aria-label="Y"><span>Y</span><em>Y</em></button><button type="button" data-button="x" aria-label="X"><span>X</span><em>X</em></button><button type="button" data-button="b" aria-label="B"><span>B</span><em>B</em></button><button type="button" data-button="a" aria-label="A"><span>A</span><em>A</em></button></div></div>
          <div class="footer"><label><input type="checkbox">接続したゲームパッドを使う</label><span>左スティック / 十字キー ＋ A B X Y</span></div>
        </fieldset>
        <p>スティックはドラッグ・タッチ・矢印キーに対応。接続したパッドはボタンを一度押して検出し、スティックとボタンを離してから操作してください。</p>
      </section>`;
    root.querySelectorAll('[data-button]').forEach(button => {
      const key = button.dataset.button;
      const label = this.getAttribute(`button-${key}-label`) || key.toUpperCase();
      button.querySelector('em').textContent = label;
      button.setAttribute('aria-label', `${key.toUpperCase()} ${label}`);
    });
    this.abort = new AbortController();
    const options = { signal: this.abort.signal };
    this.stickElement = root.querySelector('.stick');
    this.checkbox = root.querySelector('input');
    this.stickElement.addEventListener('pointerdown', e => {
      if (this.disabled || this.physical || e.button !== 0 || this.pointer !== null) return;
      e.preventDefault(); this.stickElement.focus(); this.pointer = e.pointerId;
      this.stickElement.setPointerCapture(e.pointerId); this.movePointer(e);
    }, options);
    this.stickElement.addEventListener('pointermove', e => { if (this.pointer === e.pointerId) this.movePointer(e); }, options);
    for (const event of ['pointerup', 'pointercancel', 'lostpointercapture']) {
      this.stickElement.addEventListener(event, e => { if (this.pointer === e.pointerId) this.release(); }, options);
    }
    this.stickElement.addEventListener('keydown', e => {
      if (!['ArrowUp','ArrowDown','ArrowLeft','ArrowRight'].includes(e.key) || this.disabled || this.physical) return;
      e.preventDefault(); this.keys.add(e.key); this.moveKeys();
    }, options);
    this.stickElement.addEventListener('keyup', e => {
      if (!this.keys.has(e.key)) return;
      e.preventDefault(); this.keys.delete(e.key); this.moveKeys();
    }, options);
    this.stickElement.addEventListener('blur', () => { if (this.keys.size || this.pointer !== null) this.release(); }, options);
    root.querySelectorAll('[data-button]').forEach(button => button.addEventListener('click', () => {
      this.emit({ type: 'button', button: button.dataset.button }, 'screen');
    }, options));
    this.checkbox.addEventListener('change', () => {
      this.release(false); this.emit({type:'stop'}, 'screen');
      this.physical = this.checkbox.checked; this.padId = null; this.reader.reset();
      this.status(this.physical ? 'パッドのボタンを押してください' : '画面で操作できます');
    }, options);
    const suspend = () => {
      this.release(false); this.emit({type:'stop'}, 'screen');
      this.physical = false; this.checkbox.checked = false; this.padId = null; this.reader.reset();
      this.status('入力を停止しました');
    };
    window.addEventListener('blur', suspend, options);
    document.addEventListener('visibilitychange', () => { if (document.hidden) suspend(); }, options);
    this.updateDisabled();
    this.raf = requestAnimationFrame(() => this.poll());
  }
  get disabled() { return this.hasAttribute('disabled'); }
  attributeChangedCallback(name) {
    if (!this.shadowRoot) return;
    if (name === 'disabled') { this.updateDisabled(); return; }
    const key = name.split('-')[1];
    const button = this.shadowRoot.querySelector(`[data-button="${key}"]`);
    const label = this.getAttribute(name) || key.toUpperCase();
    button.querySelector('em').textContent = label;
    button.setAttribute('aria-label', `${key.toUpperCase()} ${label}`);
  }
  updateDisabled() {
    this.release(false); this.reader.reset(); this.physical = false;
    this.checkbox.checked = false;
    this.shadowRoot.querySelector('fieldset').disabled = this.disabled;
    this.stickElement.tabIndex = this.disabled ? -1 : 0;
    this.stickElement.setAttribute('aria-disabled', String(this.disabled));
    this.status(this.disabled ? '操作無効' : '画面で操作できます');
  }
  status(text) { const el = this.shadowRoot.querySelector('.status'); if (el.textContent !== text) el.textContent = text; }
  emit(detail, source) {
    if (this.disabled) return;
    this.dispatchEvent(new CustomEvent('gar-gamepad-input', {detail:{...detail, source}, bubbles:true, composed:true}));
  }
  draw(axes) {
    const radius = (this.stickElement.clientWidth - 56) / 2;
    this.shadowRoot.querySelector('.knob').style.transform = `translate(${axes[0] * radius}px, ${axes[1] * radius}px)`;
    this.shadowRoot.querySelector('.readout').textContent = `X ${axes[0].toFixed(2)} / Y ${axes[1].toFixed(2)}`;
  }
  movePointer(e) {
    const r = this.stickElement.getBoundingClientRect();
    const axes = stick((e.clientX - r.left - r.width/2)/(r.width/2), (e.clientY - r.top - r.height/2)/(r.height/2), 0);
    this.draw(axes); this.emit({type:'axes', axes}, 'screen');
  }
  moveKeys() {
    const axes = stick(Number(this.keys.has('ArrowRight')) - Number(this.keys.has('ArrowLeft')), Number(this.keys.has('ArrowDown')) - Number(this.keys.has('ArrowUp')), 0);
    this.draw(axes); this.emit({type:'axes', axes}, 'keyboard');
  }
  release(send = true) {
    const pointer = this.pointer; this.pointer = null; this.keys.clear();
    if (pointer !== null && this.stickElement.hasPointerCapture(pointer)) this.stickElement.releasePointerCapture(pointer);
    this.draw([0,0]); if (send) this.emit({type:'stop'}, 'screen');
  }
  cancel() { this.release(false); this.reader.reset(); }
  poll() {
    if (this.physical && !this.disabled && !document.hidden) {
      try {
        if (!navigator.getGamepads) throw new Error('unsupported');
        const pads = Array.from(navigator.getGamepads());
        const pad = this.padId === null ? pads.find(p => p?.connected && p.mapping === 'standard') : pads.find(p => p?.index === this.padId);
        if (pad?.connected && pad.mapping === 'standard') {
          this.padId = pad.index;
          const inputs = this.reader.sample(pad);
          const pressedButtons = this.reader.buttons.flatMap((pressed, i) => pressed ? [['a', 'b', 'x', 'y'][i]] : []);
          for (const input of inputs) {
            // A Product may cancel this sample synchronously, including its remaining events.
            if (!this.reader.ready) break;
            if (input.type === 'axes') this.draw(input.axes);
            this.emit({ ...input, pressedButtons }, 'physical');
          }
          this.status(this.reader.ready ? `接続中 · ${pad.id}` : 'スティックとボタンを離してください');
        } else {
          if (this.padId !== null) {
            this.emit({type:'stop'}, 'physical'); this.physical = false; this.checkbox.checked = false;
            this.padId = null; this.reader.reset(); this.draw([0,0]);
            this.status('切断しました · 再度チェックして接続');
          } else this.status(pads.some(p => p?.connected) ? '標準配列のパッドに対応しています' : 'パッドのボタンを押してください');
        }
      } catch {
        this.emit({type:'stop'}, 'physical'); this.physical = false; this.checkbox.checked = false;
        this.status('このブラウザでは取得できません · 画面で操作できます');
      }
    }
    this.raf = requestAnimationFrame(() => this.poll());
  }
  disconnectedCallback() { this.release(); this.abort?.abort(); cancelAnimationFrame(this.raf); }
}
if (!customElements.get('gar-gamepad')) customElements.define('gar-gamepad', GarGamepad);
