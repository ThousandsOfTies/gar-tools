export const PCA9685_CHANNEL_COUNT = 16;

const DEFAULT_FREQUENCY_HZ = 50;
const DEFAULT_MIN_PULSE_US = 500;
const DEFAULT_MAX_PULSE_US = 2500;

function finiteNumber(value, fallback) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

export function emptyPca9685State() {
  return {
    address: 0x40,
    frequencyHz: null,
    channels: Array.from({ length: PCA9685_CHANNEL_COUNT }, (_, channel) => ({
      channel,
      on: 0,
      off: 0,
      fullOn: false,
      fullOff: true,
    })),
  };
}

export function normalisePca9685State(value) {
  const fallback = emptyPca9685State();
  if (!value || typeof value !== "object") return fallback;

  const channels = Array.from({ length: PCA9685_CHANNEL_COUNT }, (_, channel) => {
    const candidate = Array.isArray(value.channels) ? value.channels[channel] : null;
    if (!candidate || typeof candidate !== "object") return fallback.channels[channel];
    return {
      channel,
      on: Math.min(4095, Math.max(0, Math.trunc(finiteNumber(candidate.on, 0)))),
      off: Math.min(4095, Math.max(0, Math.trunc(finiteNumber(candidate.off, 0)))),
      fullOn: candidate.fullOn === true,
      fullOff: candidate.fullOff === true,
    };
  });

  const frequency = finiteNumber(value.frequencyHz, NaN);
  return {
    address: Math.min(0x7f, Math.max(0, Math.trunc(finiteNumber(value.address, 0x40)))),
    frequencyHz: frequency > 0 ? frequency : null,
    channels,
  };
}

export function pca9685StateFromMessage(message, current = emptyPca9685State(), selector = {}) {
  const matches = value => value && typeof value === 'object'
    && (selector.address === undefined || Number(value.address) === selector.address)
    && (!selector.device || !value.device || value.device === selector.device);
  if (message?.type === "init") {
    const values = message.state?.i2c?.pca9685;
    return normalisePca9685State(Array.isArray(values) ? values.find(matches) : matches(values) ? values : null);
  }
  if (message?.type === "pca9685" && matches(message)) return normalisePca9685State(message);
  return current;
}

export function channelPulse(channel, frequencyHz) {
  if (!channel || channel.fullOff) return { active: false, counts: 0, pulseUs: 0 };
  if (channel.fullOn) {
    const frequency = finiteNumber(frequencyHz, DEFAULT_FREQUENCY_HZ);
    return { active: true, counts: 4096, pulseUs: 1_000_000 / frequency };
  }

  const counts = (channel.off - channel.on + 4096) % 4096;
  const frequency = finiteNumber(frequencyHz, DEFAULT_FREQUENCY_HZ);
  return {
    active: counts > 0,
    counts,
    pulseUs: counts > 0 ? (counts * 1_000_000) / (4096 * frequency) : 0,
  };
}

export function pulseToPreviewAngle(
  pulseUs,
  minPulseUs = DEFAULT_MIN_PULSE_US,
  maxPulseUs = DEFAULT_MAX_PULSE_US,
) {
  const minimum = finiteNumber(minPulseUs, DEFAULT_MIN_PULSE_US);
  const maximum = finiteNumber(maxPulseUs, DEFAULT_MAX_PULSE_US);
  if (!(maximum > minimum)) return 90;
  const ratio = Math.min(1, Math.max(0, (finiteNumber(pulseUs, minimum) - minimum) / (maximum - minimum)));
  return ratio * 180;
}
