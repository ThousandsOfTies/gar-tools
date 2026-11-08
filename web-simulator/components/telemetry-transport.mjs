/** Read-only WebSocket telemetry with a separate, local preview state. */
export class TelemetryTransport extends EventTarget {
  constructor({ initialState = () => null, reduceMessage = (message, current) => message.type === 'init' ? message.state : current, url, retryMs = 1800 } = {}) {
    super();
    this.initialState = initialState;
    this.reduceMessage = reduceMessage;
    this.url = url;
    this.retryMs = retryMs;
    this.mode = 'demo';
    this.connected = false;
    this.socket = null;
    this.retry = null;
    this.state = initialState();
  }
  emit(type, detail) { this.dispatchEvent(new CustomEvent(type, { detail })); }
  close() {
    clearTimeout(this.retry);
    this.retry = null;
    if (this.socket) {
      this.socket.onopen = this.socket.onmessage = this.socket.onclose = this.socket.onerror = null;
      this.socket.close();
      this.socket = null;
    }
    this.connected = false;
  }
  select(mode) {
    if (!['demo', 'live'].includes(mode)) throw new RangeError('Unknown telemetry mode');
    this.close();
    this.mode = mode;
    this.state = mode === 'demo' ? this.initialState() : null;
    this.emit('connection', { mode, connected: false });
    this.emit('message', { type: 'init', state: this.state });
    if (mode === 'live') this.connect();
  }
  publish(state) {
    if (this.mode !== 'demo') return;
    this.state = state;
    this.emit('message', { type: 'init', state });
  }
  connect() {
    if (this.mode !== 'live') return;
    let url = this.url;
    if (!url) {
      if (!['http:', 'https:'].includes(globalThis.location?.protocol)) return;
      url = `${location.protocol === 'https:' ? 'wss' : 'ws'}://${location.host}/ws`;
    }
    const socket = new WebSocket(url);
    this.socket = socket;
    socket.onopen = () => {
      if (this.socket !== socket) return;
      this.connected = true;
      this.emit('connection', { mode: 'live', connected: true });
    };
    socket.onmessage = ({ data }) => {
      if (this.socket !== socket) return;
      try {
        const message = JSON.parse(data);
        if (!message || typeof message !== 'object' || typeof message.type !== 'string') return;
        this.state = this.reduceMessage(message, this.state);
        this.emit('message', message);
      } catch { /* Ignore malformed telemetry. */ }
    };
    socket.onclose = () => {
      if (this.socket !== socket) return;
      this.connected = false;
      this.state = null;
      this.emit('connection', { mode: 'live', connected: false });
      if (this.socket !== socket || this.mode !== 'live') return;
      this.emit('message', { type: 'init', state: null });
      // A connection/message listener may select another mode or dispose us.
      if (this.socket === socket && this.mode === 'live') {
        this.retry = setTimeout(() => { this.retry = null; this.connect(); }, this.retryMs);
      }
    };
    socket.onerror = () => socket.close();
  }
}
