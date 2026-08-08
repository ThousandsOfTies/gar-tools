/** Shared browser transport for product-specific GAR simulator panels. */
export class BridgeClient extends EventTarget {
  #socket = null;
  #retry = null;
  #state = null;

  constructor() {
    super();
    this.#connect();
  }

  get state() { return this.#state; }

  send(message) {
    if (this.#socket?.readyState === WebSocket.OPEN) {
      this.#socket.send(JSON.stringify(message));
    }
  }

  #connect() {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    this.#socket = new WebSocket(`${protocol}//${location.host}/ws`);
    this.#socket.addEventListener("open", () => this.#emit("connection", { connected: true }));
    this.#socket.addEventListener("close", () => {
      this.#emit("connection", { connected: false });
      clearTimeout(this.#retry);
      this.#retry = setTimeout(() => this.#connect(), 1500);
    });
    this.#socket.addEventListener("message", ({ data }) => {
      try {
        const message = JSON.parse(data);
        if (message.type === "init") this.#state = message.state;
        this.#emit("message", message);
      } catch (error) {
        console.warn("GAR bridge returned invalid JSON", error);
      }
    });
  }

  #emit(type, detail) { this.dispatchEvent(new CustomEvent(type, { detail })); }
}

export const bridgeClient = new BridgeClient();
