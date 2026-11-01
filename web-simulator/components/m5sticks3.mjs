import { GarStickCPlus2 } from './m5stickc-plus2.mjs';

/** StickS3 K150 shell: two application keys, reset is a separate hardware event.
 * Reuses the Stick family's contact/cancellation contract, not Product behavior.
 */
export class GarStickS3 extends GarStickCPlus2 {
  constructor() {
    super();
    this.shadowRoot.querySelector('.c').remove();
    const style=document.createElement('style');
    style.textContent=`
      .case{background:linear-gradient(140deg,#45494c,#171a1d);border-color:#111417;box-shadow:inset 0 2px #666b70,inset 0 -5px #111,0 18px 35px #0003}
      .face{box-shadow:0 0 0 2px #111,inset 0 0 0 1px #444}
      button{background:#30373c;color:#e7edef;border-color:#101417;box-shadow:inset 0 2px #555e63,0 2px #111}
      .a{border-radius:50%;background:#da302c;color:white}.a small{opacity:.9}
      .pins{background:repeating-linear-gradient(90deg,#292c29 0 5px,#b2a075 5px 7px)}
      .reset{left:-12px;top:20%;width:12px;height:12%;border-radius:3px}
      .mark{position:absolute;bottom:2%;left:25%;font:8px system-ui;letter-spacing:1px;color:#adb5ba}
      :host([orientation=portrait]) .a{right:27%;bottom:9%;width:46%;height:22%}
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
