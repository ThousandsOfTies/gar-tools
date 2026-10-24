/** Generic browser camera sender for a configurable JPEG WebSocket endpoint. */
const DEFAULT_WIDTH = 640;
const DEFAULT_HEIGHT = 480;
const DEFAULT_CAPTURE_FPS = 15;
const DEFAULT_DEVICE_FPS = 30;

function positiveIntegerAttribute(element, name, fallback) {
  const value = Number.parseInt(element.getAttribute(name) ?? "", 10);
  return Number.isInteger(value) && value > 0 ? value : fallback;
}

export class GarCameraInput extends HTMLElement {
  static observedAttributes = ["width", "height", "capture-fps", "device-fps", "endpoint", "label"];
  #socket;
  #stream;
  #frameTimer;
  #encoding = false;
  #listeners;

  constructor() {
    super();
    this.attachShadow({ mode: "open" }).innerHTML = `
      <style>
        :host { display: block; color: var(--gar-component-text, #e9f3f8); font: inherit; }
        * { box-sizing: border-box; }
        section { display: grid; gap: 12px; padding: 16px; border: 1px solid var(--gar-component-border, #285267); border-radius: 12px; background: var(--gar-component-panel, #0c1e2a); }
        .label { color: var(--gar-component-accent, #52d6c4); font-size: .72rem; letter-spacing: .12em; }
        video { width: 100%; max-height: 240px; background: #050a12; object-fit: contain; }
        .controls { display: flex; gap: 8px; }
        select { min-width: 0; flex: 1; padding: 10px; border: 1px solid var(--gar-component-border, #285267); border-radius: 6px; color: inherit; background: var(--gar-component-button, #132b43); }
        button { padding: 10px; border: 1px solid var(--gar-component-border, #285267); border-radius: 6px; color: inherit; background: var(--gar-component-button, #203b59); cursor: pointer; font: inherit; }
        button:focus-visible, select:focus-visible { outline: 2px solid var(--gar-component-accent, #52d6c4); outline-offset: 3px; }
        output { color: var(--gar-component-muted, #b8c6d9); font-size: .85rem; }
      </style>
      <section>
        <span class="label" data-label></span>
        <video autoplay muted playsinline></video>
        <div class="controls"><select aria-label="Camera"></select><button type="button" data-start>Start camera</button></div>
        <output data-status aria-live="polite">Camera is stopped</output>
      </section>`;
    this._label = this.shadowRoot.querySelector("[data-label]");
    this._video = this.shadowRoot.querySelector("video");
    this._select = this.shadowRoot.querySelector("select");
    this._button = this.shadowRoot.querySelector("[data-start]");
    this._status = this.shadowRoot.querySelector("[data-status]");
  }

  connectedCallback() {
    this.#listeners?.abort();
    this.#listeners = new AbortController();
    const options = { signal: this.#listeners.signal };
    this._button.addEventListener("click", () => this.start(), options);
    this._select.addEventListener("change", () => { if (this.#stream) this.start(); }, options);
    navigator.mediaDevices?.addEventListener?.("devicechange", () => this.refreshCameras(), options);
    this.renderLabel();
    this.refreshCameras();
  }

  disconnectedCallback() {
    this.#listeners?.abort();
    this.stopPipeline();
    this.#stream?.getTracks().forEach((track) => track.stop());
    this.#stream = null;
  }

  attributeChangedCallback() {
    if (this._label) this.renderLabel();
  }

  get width() { return positiveIntegerAttribute(this, "width", DEFAULT_WIDTH); }
  get height() { return positiveIntegerAttribute(this, "height", DEFAULT_HEIGHT); }
  get captureFps() { return positiveIntegerAttribute(this, "capture-fps", DEFAULT_CAPTURE_FPS); }
  get deviceFps() { return positiveIntegerAttribute(this, "device-fps", DEFAULT_DEVICE_FPS); }
  get endpoint() { return this.getAttribute("endpoint") || "/camera-input/ws"; }
  set endpoint(value) {
    if (value == null || value === "") this.removeAttribute("endpoint");
    else this.setAttribute("endpoint", String(value));
  }

  renderLabel() { this._label.textContent = this.getAttribute("label") || "CAMERA INPUT"; }

  async start() {
    this._button.disabled = true;
    try {
      this.stopPipeline();
      this.#stream?.getTracks().forEach((track) => track.stop());
      const deviceId = this._select.value;
      if (!navigator.mediaDevices?.getUserMedia) throw new Error("Camera API is unavailable");
      this.#stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { exact: this.width },
          height: { exact: this.height },
          frameRate: { ideal: this.captureFps },
          ...(deviceId ? { deviceId: { exact: deviceId } } : {}),
        },
        audio: false,
      });
      this._video.srcObject = this.#stream;
      await this.refreshCameras(this.#stream.getVideoTracks()[0]?.getSettings().deviceId);
      this.connectCameraInput();
      this._button.textContent = "Restart camera";
    } catch (error) {
      this.setStatus(`Camera error: ${error.message}`);
    } finally {
      this._button.disabled = false;
    }
  }

  async refreshCameras(selectedId = this._select.value) {
    if (!navigator.mediaDevices?.enumerateDevices) return;
    const cameras = (await navigator.mediaDevices.enumerateDevices()).filter(({ kind }) => kind === "videoinput");
    this._select.replaceChildren(new Option("Default camera", ""));
    cameras.forEach((camera, index) => this._select.add(new Option(camera.label || `Camera ${index + 1}`, camera.deviceId)));
    if ([...this._select.options].some(({ value }) => value === selectedId)) this._select.value = selectedId;
  }

  connectCameraInput() {
    const endpoint = new URL(this.endpoint, location.href);
    if (endpoint.protocol === "http:" || endpoint.protocol === "https:") {
      endpoint.protocol = endpoint.protocol === "https:" ? "wss:" : "ws:";
    }
    endpoint.search = new URLSearchParams({ width: this.width, height: this.height, fps: this.deviceFps }).toString();
    const socket = new WebSocket(endpoint);
    this.#socket = socket;
    socket.addEventListener("open", () => this.setStatus("Connecting to camera endpoint..."));
    socket.addEventListener("message", ({ data }) => {
      try {
        const message = JSON.parse(data);
        if (message.type === "ready") {
          this.setStatus(`Streaming ${message.width}x${message.height}@${message.fps}`);
          this.startFramePump();
        } else if (message.type === "error") this.setStatus(`Camera input error: ${message.error}`);
      } catch { this.setStatus("Camera input returned invalid data"); }
    });
    socket.addEventListener("close", () => {
      if (this.#socket === socket) this.setStatus("Camera input closed");
    });
  }

  startFramePump() {
    clearInterval(this.#frameTimer);
    const canvas = document.createElement("canvas");
    canvas.width = this.width;
    canvas.height = this.height;
    const context = canvas.getContext("2d");
    this.#frameTimer = setInterval(() => {
      if (this.#encoding || this.#socket?.readyState !== WebSocket.OPEN) return;
      if (this._video.readyState < HTMLMediaElement.HAVE_CURRENT_DATA) return;
      this.#encoding = true;
      context.drawImage(this._video, 0, 0, this.width, this.height);
      canvas.toBlob(async (blob) => {
        try {
          if (blob && this.#socket?.readyState === WebSocket.OPEN) this.#socket.send(await blob.arrayBuffer());
        } finally { this.#encoding = false; }
      }, "image/jpeg", .82);
    }, 1000 / this.captureFps);
  }

  stopPipeline() {
    clearInterval(this.#frameTimer);
    this.#frameTimer = undefined;
    this.#socket?.close();
    this.#socket = undefined;
    this.#encoding = false;
  }

  setStatus(text) { this._status.textContent = String(text); }
}

if (!customElements.get("gar-camera-input")) customElements.define("gar-camera-input", GarCameraInput);
