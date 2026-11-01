/** Configurable JSON WebSocket transport. Hosts own protocol meaning and connection lifetime. */
export class JsonTransport extends EventTarget {
  #socket = null;
  #retry = null;
  #active = false;
  connected = false;

  constructor({ url, reconnectMs = 1500 } = {}) {
    super();
    if (typeof url !== 'string' || !url.trim()) throw new TypeError('A WebSocket URL is required');
    this.url = url;
    this.reconnectMs = Math.max(0, Number(reconnectMs) || 0);
  }

  connect() {
    this.close();
    this.#active = true;
    this.#open();
  }

  send(message) {
    if (this.#socket?.readyState !== WebSocket.OPEN) return false;
    this.#socket.send(JSON.stringify(message));
    return true;
  }

  close() {
    this.#active = false;
    clearTimeout(this.#retry);
    this.#retry = null;
    const socket = this.#socket;
    this.#socket = null;
    socket?.close();
    const wasConnected = this.connected;
    this.connected = false;
    if (wasConnected) this.#emit('connection', { connected: false });
  }

  #open() {
    if (!this.#active) return;
    const socket = new WebSocket(this.url);
    this.#socket = socket;
    socket.addEventListener('open', () => {
      if (this.#socket !== socket) return;
      this.connected = true;
      this.#emit('connection', { connected: true });
    });
    socket.addEventListener('message', ({ data }) => {
      if (this.#socket !== socket) return;
      let message;
      try { message = JSON.parse(data); } catch { return; }
      this.#emit('message', message);
    });
    socket.addEventListener('close', () => {
      if (this.#socket !== socket) return;
      this.#socket = null;
      this.connected = false;
      this.#emit('connection', { connected: false });
      if (this.#active && !this.#socket) {
        this.#retry = setTimeout(() => { this.#retry = null; this.#open(); }, this.reconnectMs);
      }
    });
  }

  #emit(type, detail) { this.dispatchEvent(new CustomEvent(type, { detail })); }
}
