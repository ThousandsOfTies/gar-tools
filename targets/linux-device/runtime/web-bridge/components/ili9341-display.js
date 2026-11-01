import { GarDisplay } from '../gar-components/display.mjs';

/** Legacy tag alias. The Product decodes messages and calls writeFrame(bytes). */
export class GarIli9341Display extends GarDisplay {}
if (!customElements.get('gar-ili9341-display')) customElements.define('gar-ili9341-display', GarIli9341Display);
