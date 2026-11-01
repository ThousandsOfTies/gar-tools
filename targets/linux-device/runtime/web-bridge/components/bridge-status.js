import { GarConnectionStatus } from '../gar-components/connection-status.mjs';

/** Legacy tag alias. The Product injects its connection through source. */
export class GarBridgeStatus extends GarConnectionStatus {}
if (!customElements.get('gar-bridge-status')) customElements.define('gar-bridge-status', GarBridgeStatus);
