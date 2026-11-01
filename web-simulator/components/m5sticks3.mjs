import { GarStickCPlus2 } from './m5stickc-plus2.mjs';

/** StickS3 K150 shell: two application keys, reset is a separate hardware event.
 * Reuses the Stick family's contact/cancellation contract, not Product behavior.
 */
export class GarStickS3 extends GarStickCPlus2 {
  constructor() {
    super();
    this.shadowRoot.querySelector('.c').remove();
    // The real K150 has an unprinted blue bar, not the Plus2's M5 keycap.
    this.shadowRoot.querySelector('.a').textContent='';
    const style=document.createElement('style');
    style.textContent=`
      .case{background:linear-gradient(140deg,#45494c,#171a1d);border-color:#111417;box-shadow:inset 0 2px #666b70,inset 0 -5px #111,0 18px 35px #0003}
      .face{box-shadow:0 0 0 2px #111,inset 0 0 0 1px #444}
      button{background:#30373c;color:#e7edef;border-color:#101417;box-shadow:inset 0 2px #555e63,0 2px #111}
      .a{right:12%;top:24%;width:5%;height:52%;padding:0;border-radius:999px;
        background:linear-gradient(90deg,#008ebd,#17c9f4 50%,#09afe0);border:1px solid #006587;
        box-shadow:inset 2px 0 2px #70e8ff,0 0 0 3px #111a,2px 1px 3px #0009}
      .a::before{content:'';position:absolute;inset:-10px;border-radius:inherit}
      .a[aria-pressed=true]{filter:brightness(.85);transform:translateY(1px);box-shadow:inset 0 1px 3px #005d7e,0 0 0 3px #111a}
      .pins{background:repeating-linear-gradient(90deg,#292c29 0 5px,#b2a075 5px 7px)}
      .reset{left:-12px;top:20%;width:12px;height:12%;border-radius:3px}
      .mark{position:absolute;bottom:2%;left:25%;font:8px system-ui;letter-spacing:1px;color:#adb5ba}
      :host([orientation=portrait]) .a{right:24%;top:auto;bottom:18%;width:52%;height:4.5%;
        background:linear-gradient(#5cdefa,#0abced 48%,#009fd1);box-shadow:inset 0 2px 2px #8aeaff,0 0 0 3px #111a,0 3px 3px #0009}
      :host([orientation=portrait]) .a[aria-pressed=true]{box-shadow:inset 0 1px 3px #005d7e,0 0 0 3px #111a}
      :host([orientation=portrait]) .face{left:17%;top:6%;width:66%}
    `;
    this.shadowRoot.append(style);
    const mark=document.createElement('span');mark.className='mark';mark.textContent='M5StickS3';
    this.shadowRoot.querySelector('.case').append(mark);
  }
  connectedCallback() {
    super.connectedCallback();
    // Only physical A and B are inputs; C shortcuts cannot create a third key.
  }
  attributeChangedCallback(name) {
    super.attributeChangedCallback(name);
    if(!this.getAttribute('label'))this.shadowRoot.querySelector('.case').setAttribute('aria-label','M5StickS3');
  }
  press(button,source) {if(['A','B'].includes(button))super.press(button,source);}
}
if(!customElements.get('gar-sticks3'))customElements.define('gar-sticks3',GarStickS3);
