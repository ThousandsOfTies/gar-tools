'use strict';
const fs = require('node:fs/promises');
const path = require('node:path');

function deviceName(value) {
  if (typeof value !== 'string' || !/^[a-zA-Z0-9_:,=.-]{1,128}$/.test(value))
    throw new Error('Select an explicit ALSA device');
  return value;
}

/** Read kernel identities rather than persisting enumeration-dependent card numbers. */
async function devices(root = '/proc/asound') {
  let entries;
  try { entries = await fs.readdir(root); }
  catch (error) { if (error.code === 'ENOENT') return []; throw error; }
  const result = [];
  for (const entry of entries.filter(name => /^card\d+$/.test(name)).sort()) {
    const directory = path.join(root, entry);
    const id = (await fs.readFile(path.join(directory, 'id'), 'utf8')).trim();
    // Some kernel card IDs contain underscores; arbitrary control/config strings do not belong here.
    if (!/^[a-zA-Z0-9_-]+$/.test(id)) continue;
    let usb = null;
    try { usb = (await fs.readFile(path.join(directory, 'usbid'), 'utf8')).trim(); }
    catch (error) { if (error.code !== 'ENOENT') throw error; }
    const endpoints = [];
    for (const pcm of await fs.readdir(directory)) {
      const match = /^pcm(\d+)([pc])$/.exec(pcm);
      if (match) endpoints.push({direction: match[2] === 'p' ? 'playback' : 'capture',
        device: `plughw:CARD=${id},DEV=${Number(match[1])}`});
    }
    result.push({card: Number(entry.slice(4)), id, usb, endpoints});
  }
  return result;
}

async function checkWave(file, maximumBytes = 16 * 1024 * 1024) {
  const handle = await fs.open(file, 'r');
  try {
    const stat = await handle.stat(), header = Buffer.alloc(12);
    await handle.read(header, 0, header.length, 0);
    if (!stat.isFile() || stat.size <= 44 || stat.size > maximumBytes ||
        header.toString('ascii', 0, 4) !== 'RIFF' || header.toString('ascii', 8, 12) !== 'WAVE')
      throw new Error('Audio must be a nonempty bounded WAV file');
  } finally { await handle.close(); }
}

/** The caller supplies its cancellable, timeout-enforcing process runner. No shell. */
class AlsaAudio {
  constructor({job}) {
    if (typeof job !== 'function') throw new Error('ALSA needs a bounded process runner');
    this.job = job;
  }
  record(file, device, seconds) {
    deviceName(device);
    if (!Number.isInteger(seconds) || seconds < 1 || seconds > 15)
      throw new Error('Recording duration must be 1..15 seconds');
    return this.job('arecord', ['-q', '-D', device, '-t', 'wav', '-f', 'S16_LE',
      '-r', '16000', '-c', '1', '-d', String(seconds), file], {timeoutMs: seconds * 1000 + 5000});
  }
  play(file, device) {
    deviceName(device);
    return this.job('aplay', ['-q', '-D', device, file], {timeoutMs: 30000});
  }
}

module.exports = {AlsaAudio, devices, deviceName, checkWave};
