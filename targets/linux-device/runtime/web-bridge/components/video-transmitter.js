const SIGNAL_URL = "ws://127.0.0.1:8080/media-signal/ws";

class GarVideoTransmitter extends HTMLElement {
  #socket; #peer; #stream;

  connectedCallback() {
    this.innerHTML = `<section><span class="label">PC CAMERA → WEBRTC</span><video autoplay muted playsinline></video><div><button>Start camera</button><output>Camera is stopped</output></div></section>`;
    this.querySelector("button").addEventListener("click", () => this.start());
  }

  async start() {
    const button = this.querySelector("button");
    button.disabled = true;
    try {
      this.#stream = await navigator.mediaDevices.getUserMedia({ video: { width: { ideal: 640 }, height: { ideal: 480 } }, audio: false });
      this.querySelector("video").srcObject = this.#stream;
      this.#setStatus("Waiting for Rx…");
      this.#connectSignal();
    } catch (error) {
      this.#setStatus(`Camera error: ${error.message}`);
      button.disabled = false;
    }
  }

  #connectSignal() {
    this.#socket = new WebSocket(this.getAttribute("signal-url") || SIGNAL_URL);
    this.#socket.addEventListener("open", () => this.#send({ type: "register", session: "garstream", role: "tx" }));
    this.#socket.addEventListener("message", ({ data }) => this.#signal(JSON.parse(data)));
    this.#socket.addEventListener("close", () => this.#setStatus("Signal connection closed"));
  }

  async #signal(message) {
    if (message.type === "peer-ready") return this.#offer();
    if (message.type !== "signal") return;
    if (message.data.description?.type === "answer") await this.#peer?.setRemoteDescription(message.data.description);
    if (message.data.candidate) await this.#peer?.addIceCandidate(message.data.candidate);
  }

  async #offer() {
    if (this.#peer) this.#peer.close();
    this.#peer = new RTCPeerConnection();
    this.#stream.getTracks().forEach((track) => this.#peer.addTrack(track, this.#stream));
    this.#peer.addEventListener("icecandidate", ({ candidate }) => { if (candidate) this.#send({ type: "signal", data: { candidate } }); });
    this.#peer.addEventListener("connectionstatechange", () => this.#setStatus(`Rx: ${this.#peer.connectionState}`));
    const offer = await this.#peer.createOffer();
    await this.#peer.setLocalDescription(offer);
    this.#send({ type: "signal", data: { description: this.#peer.localDescription } });
  }

  #send(message) { if (this.#socket?.readyState === WebSocket.OPEN) this.#socket.send(JSON.stringify(message)); }
  #setStatus(text) { this.querySelector("output").textContent = text; }
}
customElements.define("gar-video-transmitter", GarVideoTransmitter);
