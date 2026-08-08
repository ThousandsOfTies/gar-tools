const SIGNAL_URL = "ws://127.0.0.1:8080/media-signal/ws";

class GarVideoReceiver extends HTMLElement {
  #socket; #peer;

  connectedCallback() {
    this.innerHTML = `<section><span class="label">WEBRTC VIDEO FROM TX</span><video autoplay playsinline></video><output>Waiting for Tx…</output></section>`;
    this.#socket = new WebSocket(this.getAttribute("signal-url") || SIGNAL_URL);
    this.#socket.addEventListener("open", () => this.#send({ type: "register", session: "garstream", role: "rx" }));
    this.#socket.addEventListener("message", ({ data }) => this.#signal(JSON.parse(data)));
    this.#socket.addEventListener("close", () => this.#setStatus("Signal connection closed"));
  }

  async #signal(message) {
    if (message.type !== "signal") return;
    const data = message.data;
    if (data.description?.type === "offer") {
      if (this.#peer) this.#peer.close();
      this.#peer = new RTCPeerConnection();
      this.#peer.addEventListener("icecandidate", ({ candidate }) => { if (candidate) this.#send({ type: "signal", data: { candidate } }); });
      this.#peer.addEventListener("track", ({ streams }) => { this.querySelector("video").srcObject = streams[0]; this.#setStatus("Receiving Tx camera"); });
      await this.#peer.setRemoteDescription(data.description);
      const answer = await this.#peer.createAnswer();
      await this.#peer.setLocalDescription(answer);
      this.#send({ type: "signal", data: { description: this.#peer.localDescription } });
    } else if (data.candidate) {
      await this.#peer?.addIceCandidate(data.candidate);
    }
  }

  #send(message) { if (this.#socket?.readyState === WebSocket.OPEN) this.#socket.send(JSON.stringify(message)); }
  #setStatus(text) { this.querySelector("output").textContent = text; }
}
customElements.define("gar-video-receiver", GarVideoReceiver);
