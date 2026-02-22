const NOTE_NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"];
const SCALE_INTERVALS = {
  minor: [0, 2, 3, 5, 7, 8, 10],
  dorian: [0, 2, 3, 5, 7, 9, 10],
  minorPent: [0, 3, 5, 7, 10]
};

const PRESETS = [
  { name: "Night Tape", tempo: 72, swing: 14, key: "D", scale: "minor", bars: 4, density: 58, seed: "night-tape-72" },
  { name: "Rain Window", tempo: 68, swing: 18, key: "F", scale: "minor", bars: 4, density: 52, seed: "rain-window-68" },
  { name: "Dusk Walk", tempo: 76, swing: 12, key: "A", scale: "dorian", bars: 4, density: 64, seed: "dusk-walk-76" },
  { name: "Cozy Corner", tempo: 64, swing: 20, key: "C", scale: "minorPent", bars: 4, density: 49, seed: "cozy-corner-64" },
  { name: "Dusty Grooves", tempo: 82, swing: 11, key: "G", scale: "minor", bars: 6, density: 70, seed: "dusty-grooves-82" },
  { name: "Subway Lights", tempo: 88, swing: 9, key: "E", scale: "minor", bars: 4, density: 73, seed: "subway-lights-88" },
  { name: "Cafe Late", tempo: 74, swing: 16, key: "B", scale: "dorian", bars: 5, density: 61, seed: "cafe-late-74" },
  { name: "Moon Study", tempo: 60, swing: 22, key: "F#", scale: "minorPent", bars: 4, density: 44, seed: "moon-study-60" },
  { name: "Neon Drift", tempo: 96, swing: 8, key: "C#", scale: "minor", bars: 6, density: 76, seed: "neon-drift-96" },
  { name: "Morning Transit", tempo: 108, swing: 6, key: "G#", scale: "dorian", bars: 4, density: 68, seed: "morning-transit-108" }
];

const state = {
  audioCtx: null,
  master: null,
  timerId: null,
  adaptiveTimerId: null,
  isPlaying: false,
  nextNoteTime: 0,
  currentStep: 0,
  pattern: null,
  baseTempo: 96,
  liveTempo: 96,
  liveMetrics: null,
  stepsPerBar: 16,
  scheduleAheadTime: 0.12,
  lookaheadMs: 25
};

const ui = {
  tempo: document.getElementById("tempo"),
  tempoValue: document.getElementById("tempoValue"),
  swing: document.getElementById("swing"),
  swingValue: document.getElementById("swingValue"),
  key: document.getElementById("key"),
  scale: document.getElementById("scale"),
  bars: document.getElementById("bars"),
  presetSelect: document.getElementById("presetSelect"),
  loadPreset: document.getElementById("loadPreset"),
  density: document.getElementById("density"),
  densityValue: document.getElementById("densityValue"),
  seed: document.getElementById("seed"),
  insKeys: document.getElementById("insKeys"),
  insBass: document.getElementById("insBass"),
  insPad: document.getElementById("insPad"),
  insKick: document.getElementById("insKick"),
  insSnare: document.getElementById("insSnare"),
  insHat: document.getElementById("insHat"),
  adaptiveBpm: document.getElementById("adaptiveBpm"),
  perfReadout: document.getElementById("perfReadout"),
  initAudio: document.getElementById("initAudio"),
  generate: document.getElementById("generate"),
  play: document.getElementById("play"),
  stop: document.getElementById("stop"),
  status: document.getElementById("status"),
  patternView: document.getElementById("patternView")
};

function setStatus(text) {
  ui.status.textContent = text;
}

function queryParams() {
  return new URLSearchParams(window.location.search);
}

function hashStringToInt(str) {
  let h = 1779033703 ^ str.length;
  for (let i = 0; i < str.length; i++) {
    h = Math.imul(h ^ str.charCodeAt(i), 3432918353);
    h = (h << 13) | (h >>> 19);
  }
  return (h >>> 0) || 1;
}

function mulberry32(a) {
  return function random() {
    let t = (a += 0x6d2b79f5);
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

function formatPct(value) {
  if (typeof value !== "number" || Number.isNaN(value)) return "--";
  return `${Math.round(value)}%`;
}

function updatePerfReadout() {
  if (!state.liveMetrics) {
    ui.perfReadout.textContent = `CPU -- | RAM -- | GPU -- | VRAM -- | Live BPM ${Math.round(state.liveTempo)}`;
    return;
  }
  const m = state.liveMetrics;
  ui.perfReadout.textContent =
    `CPU ${formatPct(m.cpu)} | RAM ${formatPct(m.ram)} | GPU ${formatPct(m.gpu)} | VRAM ${formatPct(m.vram)} | Live BPM ${Math.round(state.liveTempo)}`;
}

function metricsToTempo(baseTempo, metrics) {
  const cpu = clamp(metrics.cpu || 0, 0, 100);
  const ram = clamp(metrics.ram || 0, 0, 100);
  const gpu = clamp(metrics.gpu || 0, 0, 100);
  const vram = clamp(metrics.vram || 0, 0, 100);
  const weightedLoad = (cpu * 0.34) + (ram * 0.2) + (gpu * 0.27) + (vram * 0.19);
  const delta = ((weightedLoad / 100) * 40) - 10;
  return clamp(baseTempo + delta, 54, 128);
}

async function fetchMetricsAndUpdateTempo() {
  try {
    const res = await fetch("/api/metrics", { cache: "no-store" });
    if (!res.ok) throw new Error(`metrics HTTP ${res.status}`);
    const metrics = await res.json();
    state.liveMetrics = metrics;
    const targetTempo = metricsToTempo(state.baseTempo, metrics);
    state.liveTempo += 0.2 * (targetTempo - state.liveTempo);
    state.liveTempo = clamp(state.liveTempo, 54, 128);
    ui.tempo.value = String(Math.round(state.liveTempo));
    ui.tempoValue.textContent = ui.tempo.value;
    updatePerfReadout();
  } catch (_err) {
    state.liveMetrics = null;
    state.liveTempo += 0.1 * (state.baseTempo - state.liveTempo);
    updatePerfReadout();
  }
}

function stopAdaptiveTempo() {
  if (state.adaptiveTimerId) {
    clearInterval(state.adaptiveTimerId);
    state.adaptiveTimerId = null;
  }
  state.liveMetrics = null;
  state.liveTempo = state.baseTempo;
  updatePerfReadout();
}

function startAdaptiveTempo() {
  stopAdaptiveTempo();
  state.adaptiveTimerId = setInterval(fetchMetricsAndUpdateTempo, 1000);
  fetchMetricsAndUpdateTempo();
}

function midiToFreq(midi) {
  return 440 * Math.pow(2, (midi - 69) / 12);
}

function buildScalePitches(keyName, scaleName, minOctave, maxOctave) {
  const root = NOTE_NAMES.indexOf(keyName);
  const intervals = SCALE_INTERVALS[scaleName];
  const notes = [];
  for (let oct = minOctave; oct <= maxOctave; oct++) {
    const base = oct * 12;
    for (const step of intervals) {
      notes.push(base + root + step);
    }
  }
  return notes.sort((a, b) => a - b);
}

function nearestIndexByValue(values, target) {
  let best = 0;
  let dist = Infinity;
  for (let i = 0; i < values.length; i++) {
    const d = Math.abs(values[i] - target);
    if (d < dist) {
      best = i;
      dist = d;
    }
  }
  return best;
}

function chooseWeighted(rng, items) {
  const total = items.reduce((sum, x) => sum + x.weight, 0);
  const pick = rng() * total;
  let run = 0;
  for (const item of items) {
    run += item.weight;
    if (pick <= run) {
      return item.value;
    }
  }
  return items[items.length - 1].value;
}

function euclideanPattern(pulses, steps) {
  if (pulses <= 0) return new Array(steps).fill(false);
  if (pulses >= steps) return new Array(steps).fill(true);

  const pattern = [];
  let bucket = 0;
  for (let i = 0; i < steps; i++) {
    bucket += pulses;
    if (bucket >= steps) {
      bucket -= steps;
      pattern.push(true);
    } else {
      pattern.push(false);
    }
  }
  return pattern;
}

function buildChordDegrees(barCount, rng, scaleLength) {
  const choices = [0, 3, 5, 4, 6, 2];
  const degrees = [];
  let current = chooseWeighted(rng, [
    { value: 0, weight: 5 },
    { value: 5 % scaleLength, weight: 2 },
    { value: 3 % scaleLength, weight: 2 }
  ]);

  for (let i = 0; i < barCount; i++) {
    degrees.push(current % scaleLength);
    current = chooseWeighted(rng, choices.map((c) => ({
      value: c,
      weight: c === 0 ? 2 : Math.max(1, 6 - Math.abs(c - current))
    })));
  }

  degrees[barCount - 1] = 0;
  return degrees;
}

function chordFromDegree(scalePitches, degree, targetMidi) {
  const scaleLength = SCALE_INTERVALS[ui.scale.value].length;
  const baseIndex = degree + scaleLength * 2;

  const indexes = [baseIndex, baseIndex + 2, baseIndex + 4, baseIndex + 6];
  const chord = indexes.map((idx) => scalePitches[idx % scalePitches.length]);

  const offset = targetMidi - chord[0];
  const semis = Math.round(offset / 12) * 12;
  return chord.map((n) => n + semis);
}

function mutateMotif(rng, motif, chordTones) {
  return motif.map((note) => {
    if (note === null) return null;
    if (rng() < 0.2) {
      return chordTones[Math.floor(rng() * chordTones.length)];
    }
    if (rng() < 0.24) {
      return note + chooseWeighted(rng, [
        { value: -2, weight: 1 },
        { value: -1, weight: 2 },
        { value: 1, weight: 2 },
        { value: 2, weight: 1 }
      ]);
    }
    return note;
  });
}

function generatePattern(config) {
  const rng = mulberry32(hashStringToInt(config.seed));
  const totalSteps = config.bars * state.stepsPerBar;
  const melodyScale = buildScalePitches(config.key, config.scale, 4, 6);
  const chordScale = buildScalePitches(config.key, config.scale, 3, 5);
  const bassScale = buildScalePitches(config.key, config.scale, 2, 3);

  const chordDegrees = buildChordDegrees(config.bars, rng, SCALE_INTERVALS[config.scale].length);

  const tracks = {
    keys: [],
    bass: [],
    pad: [],
    kick: [],
    snare: [],
    hat: []
  };

  const motifLength = 16;
  let motif = new Array(motifLength).fill(null).map(() => {
    if (rng() > config.density * 0.9) return null;
    const pick = Math.floor(rng() * melodyScale.length);
    return melodyScale[clamp(pick, 3, melodyScale.length - 4)];
  });

  for (let bar = 0; bar < config.bars; bar++) {
    const barStart = bar * state.stepsPerBar;
    const degree = chordDegrees[bar];
    const chord = chordFromDegree(chordScale, degree, 60 + (bar % 2) * 2);

    tracks.pad.push({
      step: barStart,
      dur: 14,
      midi: chord,
      vel: 0.45 + rng() * 0.1
    });

    const keyHits = [0, 4, 8, 12].filter(() => rng() < 0.82);
    for (const hit of keyHits) {
      const inversion = chooseWeighted(rng, [
        { value: 0, weight: 5 },
        { value: 1, weight: 3 },
        { value: 2, weight: 1 }
      ]);

      const voiced = chord.map((n, i) => n + (i < inversion ? 12 : 0));
      tracks.keys.push({
        step: barStart + hit,
        dur: 3,
        midi: voiced,
        vel: 0.54 + rng() * 0.18
      });
    }

    const root = bassScale[nearestIndexByValue(bassScale, chord[0] - 12)];
    tracks.bass.push({ step: barStart + 0, dur: 6, midi: [root], vel: 0.62 + rng() * 0.14 });
    tracks.bass.push({ step: barStart + 8, dur: 6, midi: [root + (rng() < 0.25 ? 7 : 0)], vel: 0.56 + rng() * 0.16 });

    motif = mutateMotif(rng, motif, chord);
    for (let i = 0; i < motifLength; i++) {
      const globalStep = barStart + i;
      if (globalStep >= totalSteps) continue;
      if (rng() > config.density) continue;
      const midi = motif[i];
      if (midi === null) continue;
      const dur = rng() < 0.72 ? 1 : 2;
      tracks.keys.push({
        step: globalStep,
        dur,
        midi: [clamp(midi + chooseWeighted(rng, [
          { value: -12, weight: 1 },
          { value: 0, weight: 7 },
          { value: 12, weight: 2 }
        ]), 52, 88)],
        vel: 0.35 + rng() * 0.33
      });
    }
  }

  for (let bar = 0; bar < config.bars; bar++) {
    const start = bar * state.stepsPerBar;
    const kickPattern = euclideanPattern(4 + Math.floor(rng() * 2), state.stepsPerBar);
    const hatPattern = euclideanPattern(10 + Math.floor(rng() * 4), state.stepsPerBar);

    for (let s = 0; s < state.stepsPerBar; s++) {
      if (kickPattern[s] && (s === 0 || rng() < 0.7)) {
        tracks.kick.push({ step: start + s, vel: 0.6 + rng() * 0.25 });
      }
      if (s === 4 || s === 12 || (rng() < 0.06 && s % 4 === 0)) {
        tracks.snare.push({ step: start + s, vel: 0.45 + rng() * 0.2 });
      }
      if (hatPattern[s] && rng() < 0.9) {
        tracks.hat.push({ step: start + s, vel: 0.16 + rng() * 0.28 });
      }
    }
  }

  return {
    config,
    totalSteps,
    tracks
  };
}

function ensureAudio() {
  if (state.audioCtx) return;
  const ctx = new (window.AudioContext || window.webkitAudioContext)();
  const master = ctx.createGain();
  master.gain.value = 0.78;
  master.connect(ctx.destination);

  state.audioCtx = ctx;
  state.master = master;
}

function envGain(ctx, start, attack, peak, release) {
  const gain = ctx.createGain();
  gain.gain.cancelScheduledValues(start);
  gain.gain.setValueAtTime(0.0001, start);
  gain.gain.linearRampToValueAtTime(peak, start + attack);
  gain.gain.exponentialRampToValueAtTime(0.0001, start + attack + release);
  return gain;
}

function playKeys(freq, when, durSec, vel) {
  const ctx = state.audioCtx;
  const gain = envGain(ctx, when, 0.01, 0.14 * vel, Math.max(0.13, durSec * 0.95));
  const filter = ctx.createBiquadFilter();
  filter.type = "lowpass";
  filter.frequency.setValueAtTime(2200, when);
  filter.Q.setValueAtTime(0.7, when);

  const o1 = ctx.createOscillator();
  o1.type = "triangle";
  o1.frequency.setValueAtTime(freq, when);

  const o2 = ctx.createOscillator();
  o2.type = "sine";
  o2.frequency.setValueAtTime(freq * 2, when);
  o2.detune.setValueAtTime(-6, when);

  o1.connect(filter);
  o2.connect(filter);
  filter.connect(gain);
  gain.connect(state.master);

  o1.start(when);
  o2.start(when);
  o1.stop(when + durSec + 0.25);
  o2.stop(when + durSec + 0.25);
}

function playBass(freq, when, durSec, vel) {
  const ctx = state.audioCtx;
  const gain = envGain(ctx, when, 0.005, 0.24 * vel, Math.max(0.16, durSec * 0.9));
  const filter = ctx.createBiquadFilter();
  filter.type = "lowpass";
  filter.frequency.setValueAtTime(420, when);
  filter.Q.setValueAtTime(1.2, when);

  const sub = ctx.createOscillator();
  sub.type = "sine";
  sub.frequency.setValueAtTime(freq * 0.5, when);

  const main = ctx.createOscillator();
  main.type = "sawtooth";
  main.frequency.setValueAtTime(freq, when);

  sub.connect(filter);
  main.connect(filter);
  filter.connect(gain);
  gain.connect(state.master);

  sub.start(when);
  main.start(when);
  sub.stop(when + durSec + 0.3);
  main.stop(when + durSec + 0.3);
}

function playPad(freq, when, durSec, vel) {
  const ctx = state.audioCtx;
  const gain = envGain(ctx, when, 0.14, 0.08 * vel, Math.max(0.4, durSec));
  const filter = ctx.createBiquadFilter();
  filter.type = "lowpass";
  filter.frequency.setValueAtTime(1500, when);

  const left = ctx.createOscillator();
  left.type = "triangle";
  left.frequency.setValueAtTime(freq, when);
  left.detune.setValueAtTime(-5, when);

  const right = ctx.createOscillator();
  right.type = "triangle";
  right.frequency.setValueAtTime(freq, when);
  right.detune.setValueAtTime(5, when);

  left.connect(filter);
  right.connect(filter);
  filter.connect(gain);
  gain.connect(state.master);

  left.start(when);
  right.start(when);
  left.stop(when + durSec + 0.45);
  right.stop(when + durSec + 0.45);
}

function playKick(when, vel) {
  const ctx = state.audioCtx;
  const osc = ctx.createOscillator();
  osc.type = "sine";
  osc.frequency.setValueAtTime(145, when);
  osc.frequency.exponentialRampToValueAtTime(45, when + 0.14);

  const gain = envGain(ctx, when, 0.001, 0.95 * vel, 0.16);
  osc.connect(gain);
  gain.connect(state.master);

  osc.start(when);
  osc.stop(when + 0.19);
}

function playSnare(when, vel) {
  const ctx = state.audioCtx;
  const toneA = ctx.createOscillator();
  toneA.type = "triangle";
  toneA.frequency.setValueAtTime(180, when);

  const toneB = ctx.createOscillator();
  toneB.type = "square";
  toneB.frequency.setValueAtTime(330, when);

  const gain = envGain(ctx, when, 0.001, 0.38 * vel, 0.11);
  toneA.connect(gain);
  toneB.connect(gain);
  gain.connect(state.master);

  toneA.start(when);
  toneB.start(when);
  toneA.stop(when + 0.14);
  toneB.stop(when + 0.14);
}

function playHat(when, vel) {
  const ctx = state.audioCtx;
  const osc = ctx.createOscillator();
  osc.type = "square";
  osc.frequency.setValueAtTime(2600, when);

  const hp = ctx.createBiquadFilter();
  hp.type = "highpass";
  hp.frequency.setValueAtTime(3200, when);

  const gain = envGain(ctx, when, 0.001, 0.12 * vel, 0.035);
  osc.connect(hp);
  hp.connect(gain);
  gain.connect(state.master);

  osc.start(when);
  osc.stop(when + 0.05);
}

function getConfigFromUI() {
  return {
    tempo: Number(ui.tempo.value),
    swing: Number(ui.swing.value) / 100,
    key: ui.key.value,
    scale: ui.scale.value,
    bars: clamp(Number(ui.bars.value) || 4, 2, 8),
    density: Number(ui.density.value) / 100,
    seed: (ui.seed.value || "lofi-default").trim(),
    instruments: {
      keys: ui.insKeys.checked,
      bass: ui.insBass.checked,
      pad: ui.insPad.checked,
      kick: ui.insKick.checked,
      snare: ui.insSnare.checked,
      hat: ui.insHat.checked
    }
  };
}

function eventsAtStep(events, step) {
  return events.filter((e) => e.step === step);
}

function scheduleStep(step, time) {
  if (!state.pattern || !state.audioCtx) return;

  const cfg = state.pattern.config;
  const effectiveTempo = ui.adaptiveBpm.checked ? state.liveTempo : cfg.tempo;
  const sixteenthSec = (60 / effectiveTempo) / 4;

  if (cfg.instruments.pad) {
    for (const e of eventsAtStep(state.pattern.tracks.pad, step)) {
      const dur = e.dur * sixteenthSec;
      for (const midi of e.midi) {
        playPad(midiToFreq(midi), time, dur, e.vel);
      }
    }
  }

  if (cfg.instruments.keys) {
    for (const e of eventsAtStep(state.pattern.tracks.keys, step)) {
      const dur = e.dur * sixteenthSec;
      for (const midi of e.midi) {
        playKeys(midiToFreq(midi), time, dur, e.vel);
      }
    }
  }

  if (cfg.instruments.bass) {
    for (const e of eventsAtStep(state.pattern.tracks.bass, step)) {
      const dur = e.dur * sixteenthSec;
      for (const midi of e.midi) {
        playBass(midiToFreq(midi), time, dur, e.vel);
      }
    }
  }

  if (cfg.instruments.kick) {
    for (const e of eventsAtStep(state.pattern.tracks.kick, step)) {
      playKick(time, e.vel);
    }
  }

  if (cfg.instruments.snare) {
    for (const e of eventsAtStep(state.pattern.tracks.snare, step)) {
      playSnare(time, e.vel);
    }
  }

  if (cfg.instruments.hat) {
    for (const e of eventsAtStep(state.pattern.tracks.hat, step)) {
      playHat(time, e.vel);
    }
  }
}

function nextStep() {
  const cfg = state.pattern.config;
  const effectiveTempo = ui.adaptiveBpm.checked ? state.liveTempo : cfg.tempo;
  const sixteenthSec = (60 / effectiveTempo) / 4;
  const swingShift = cfg.swing * sixteenthSec * 0.42;

  if (state.currentStep % 2 === 0) {
    state.nextNoteTime += sixteenthSec + swingShift;
  } else {
    state.nextNoteTime += sixteenthSec - swingShift;
  }

  state.currentStep = (state.currentStep + 1) % state.pattern.totalSteps;
}

function scheduler() {
  while (state.nextNoteTime < state.audioCtx.currentTime + state.scheduleAheadTime) {
    scheduleStep(state.currentStep, state.nextNoteTime);
    nextStep();
  }
}

function renderPattern(pattern) {
  const rows = [];
  rows.push(`Seed: ${pattern.config.seed}`);
  rows.push(`Key/Scale: ${pattern.config.key} ${pattern.config.scale}`);
  const liveTag = ui.adaptiveBpm.checked ? ` -> live ${Math.round(state.liveTempo)} BPM` : "";
  rows.push(`Tempo: ${pattern.config.tempo} BPM${liveTag} | Swing: ${Math.round(pattern.config.swing * 100)}% | Bars: ${pattern.config.bars}`);
  rows.push("");

  const trackNames = ["pad", "keys", "bass", "kick", "snare", "hat"];
  for (const name of trackNames) {
    const line = new Array(pattern.totalSteps).fill(".");
    for (const e of pattern.tracks[name]) {
      line[e.step] = name === "kick" ? "K" : name === "snare" ? "S" : name === "hat" ? "H" : "X";
    }

    const chunks = [];
    for (let i = 0; i < line.length; i += state.stepsPerBar) {
      chunks.push(line.slice(i, i + state.stepsPerBar).join(""));
    }
    rows.push(`${name.padEnd(5, " ")} ${chunks.join(" | ")}`);
  }

  ui.patternView.textContent = rows.join("\n");
}

function applyPreset(preset) {
  ui.tempo.value = String(preset.tempo);
  ui.swing.value = String(preset.swing);
  ui.key.value = preset.key;
  ui.scale.value = preset.scale;
  ui.bars.value = String(preset.bars);
  ui.density.value = String(preset.density);
  ui.seed.value = preset.seed;
  ui.tempoValue.textContent = ui.tempo.value;
  ui.swingValue.textContent = ui.swing.value;
  ui.densityValue.textContent = ui.density.value;
}

function populatePresets() {
  ui.presetSelect.innerHTML = "";
  PRESETS.forEach((preset, index) => {
    const option = document.createElement("option");
    option.value = String(index);
    option.textContent = `${index + 1}. ${preset.name}`;
    ui.presetSelect.appendChild(option);
  });
}

function generateFromUI() {
  const cfg = getConfigFromUI();
  state.pattern = generatePattern(cfg);
  renderPattern(state.pattern);
  setStatus(`Generated ${cfg.bars} bars in ${cfg.key} ${cfg.scale} using seed "${cfg.seed}".`);
}

function startPlayback() {
  if (!state.audioCtx) {
    setStatus("Click Enable Audio first.");
    return;
  }
  if (!state.pattern) {
    generateFromUI();
  }
  if (state.isPlaying) return;

  if (state.audioCtx.state === "suspended") {
    state.audioCtx.resume();
  }

  state.isPlaying = true;
  state.currentStep = 0;
  state.nextNoteTime = state.audioCtx.currentTime + 0.05;
  state.timerId = setInterval(scheduler, state.lookaheadMs);
  setStatus("Playing generated loop.");
}

function stopPlayback() {
  state.isPlaying = false;
  if (state.timerId) {
    clearInterval(state.timerId);
    state.timerId = null;
  }
  setStatus("Stopped.");
}

function wireUI() {
  const bindLiveValue = (input, output) => {
    const update = () => {
      output.textContent = input.value;
    };
    input.addEventListener("input", update);
    update();
  };

  bindLiveValue(ui.tempo, ui.tempoValue);
  bindLiveValue(ui.swing, ui.swingValue);
  bindLiveValue(ui.density, ui.densityValue);

  ui.loadPreset.addEventListener("click", () => {
    const index = Number(ui.presetSelect.value) || 0;
    const preset = PRESETS[index];
    applyPreset(preset);
    generateFromUI();
    setStatus(`Loaded preset: ${preset.name}`);
  });

  ui.presetSelect.addEventListener("change", () => {
    const index = Number(ui.presetSelect.value) || 0;
    applyPreset(PRESETS[index]);
  });

  ui.initAudio.addEventListener("click", () => {
    try {
      ensureAudio();
      state.audioCtx.resume();
      setStatus("Audio initialized.");
    } catch (err) {
      setStatus(`Audio failed: ${err.message}`);
    }
  });

  ui.generate.addEventListener("click", () => {
    generateFromUI();
  });

  ui.play.addEventListener("click", () => {
    startPlayback();
  });

  ui.stop.addEventListener("click", () => {
    stopPlayback();
  });
}

populatePresets();
applyPreset(PRESETS[0]);
wireUI();
generateFromUI();
