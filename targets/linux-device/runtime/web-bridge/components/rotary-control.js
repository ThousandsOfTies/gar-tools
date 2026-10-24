import { GarRotary } from '../gar-components/rotary.mjs';

/** Legacy tag alias. The Product handles gar-rotary-input and sets value. */
export class GarRotaryControl extends GarRotary {}
if (!customElements.get('gar-rotary-control')) customElements.define('gar-rotary-control', GarRotaryControl);
