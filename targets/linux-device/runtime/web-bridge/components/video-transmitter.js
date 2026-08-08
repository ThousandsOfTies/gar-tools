const CAMERA_WIDTH = 640;
const CAMERA_HEIGHT = 480;
const CAMERA_FPS = 15;

class GarVideoTransmitter extends HTMLElement {
  #socket; #stream; #frameTimer; #encoding = false;

  connectedCallback() {
    this.innerHTML = `<section><span class="label">PC CAMERA → TX EC2 /dev/video0</span><video autoplay muted playsinline></video><div class="camera-controls"><select aria-label="Camera"><option value="">Default camera</option></select><button>Start camera</button></div><output>Camera is stopped</output></section>`;
    this.querySelector("button").addEventListener("click", () => this.start());
    this.querySelector("select").addEventListener("change", () => { if (this.#stream) this.start(); });
    navigator.mediaDevices?.addEventListener("devicechange", () => this.#refreshCameras());
    this.#refreshCameras();
  }

  disconnectedCallback() {
    this.#stopPipeline();
    this.#stream?.getTracks().forEach((track) => track.stop());
  }

  async start() {
    const button = this.querySelector("button");
    button.disabled = true;
    try {
      this.#stopPipeline();
      this.#stream?.getTracks().forEach((track) => track.stop());
      const deviceId = this.querySelector("select").value;
      this.#stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: CAMERA_WIDTH },
          height: { ideal: CAMERA_HEIGHT },
          frameRate: { ideal: CAMERA_FPS },
          ...(deviceId ? { deviceId: { exact: deviceId } } : {}),
        },
        audio: false,
      });
      this.querySelector("video").srcObject = this.#stream;
      await this.#refreshCameras(this.#stream.getVideoTracks()[0]?.getSettings().deviceId);
      this.#connectCameraInput();
      button.textContent = "Restart camera";
      button.disabled = false;
    } catch (error) {
      this.#setStatus(`Camera error: ${error.message}`);
      button.disabled = false;
    }
  }

  async #refreshCameras(selectedId = this.querySelector("select").value) {
    if (!navigator.mediaDevices?.enumerateDevices) return;
    const cameras = (await navigator.mediaDevices.enumerateDevices()).filter(({ kind }) => kind === "videoinput");
    const select = this.querySelector("select");
    select.replaceChildren(new Option("Default camera", ""));
    cameras.forEach((camera, index) => select.add(new Option(camera.label || `Camera ${index + 1}`, camera.deviceId)));
    if ([...select.options].some(({ value }) => value === selectedId)) select.value = selectedId;
  }

  #connectCameraInput() {
    const protocol = location.protocol === "https:" ? "wss:" : "ws:";
    const socket = new WebSocket(`${protocol}//${location.host}/camera-input/ws`);
    this.#socket = socket;
    socket.addEventListener("open", () => this.#setStatus("Connecting to Tx EC2 camera device…"));
    socket.addEventListener("message", ({ data }) => {
      const message = JSON.parse(data);
      if (message.type === "ready") {
        this.#setStatus(`Streaming to Tx EC2 ${message.device}`);
        this.#startFramePump();
      } else if (message.type === "error") {
        this.#setStatus(`Camera input error: ${message.error}`);
      }
    });
    socket.addEventListener("close", () => {
      if (this.#socket === socket) this.#setStatus("Tx EC2 camera input closed");
    });
  }

  #startFramePump() {
    clearInterval(this.#frameTimer);
    const canvas = document.createElement("canvas");
    canvas.width = CAMERA_WIDTH;
    canvas.height = CAMERA_HEIGHT;
    const context = canvas.getContext("2d");
    this.#frameTimer = setInterval(() => {
      if (this.#encoding || this.#socket?.readyState !== WebSocket.OPEN) return;
      const video = this.querySelector("video");
      if (video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return;
      this.#encoding = true;
      context.drawImage(video, 0, 0, CAMERA_WIDTH, CAMERA_HEIGHT);
      canvas.toBlob(async (blob) => {
        try {
          if (blob && this.#socket?.readyState === WebSocket.OPEN) this.#socket.send(await blob.arrayBuffer());
        } finally {
          this.#encoding = false;
        }
      }, "image/jpeg", 0.82);
    }, 1000 / CAMERA_FPS);
  }

  #stopPipeline() {
    clearInterval(this.#frameTimer);
    this.#frameTimer = undefined;
    this.#socket?.close();
    this.#socket = undefined;
    this.#encoding = false;
  }

  #setStatus(text) { this.querySelector("output").textContent = text; }
}
customElements.define("gar-video-transmitter", GarVideoTransmitter);
