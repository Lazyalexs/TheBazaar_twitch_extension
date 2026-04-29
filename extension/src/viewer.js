import { formatValue, parseEnvelope, titleCase } from "./protocol.js";

const refs = {
  hero: document.querySelector("#hero"),
  status: document.querySelector("#status"),
  day: document.querySelector("#day"),
  gold: document.querySelector("#gold"),
  health: document.querySelector("#health"),
  phase: document.querySelector("#phase"),
  board: document.querySelector("#board"),
  tooltip: document.querySelector("#tooltip"),
};

const state = {
  items: new Map(),
  latestSeq: -1,
  latestRunId: null,
  latestEnvelope: null,
  localPollTimer: null,
  twitchChannelId: null,
  hideTooltipTimer: null,
};

async function loadReferenceData() {
  const response = await fetch("./data/items.min.json");
  const items = await response.json();
  state.items = new Map(items.map((item) => [item.id, item]));
}

function setStatus(text) {
  refs.status.textContent = text;
}

function tierLabel(value) {
  return value ? `${titleCase(value)}+` : "Item";
}

function tagsFor(ref, itemState) {
  const tags = [
    tierLabel(itemState.tier ?? ref?.baseTier),
    ...(ref?.tags ?? []),
    ...(ref?.heroes ?? []),
  ];
  return tags.filter(Boolean);
}

function renderArt(ref) {
  const art = document.createElement("div");
  art.className = "tooltip-art";
  if (ref?.image) {
    art.style.backgroundImage = `url("${ref.image}")`;
  }
  return art;
}

function renderPillList(items) {
  const wrap = document.createElement("div");
  wrap.className = "tooltip-pills";
  for (const item of items) {
    const pill = document.createElement("span");
    pill.textContent = titleCase(item);
    wrap.append(pill);
  }
  return wrap;
}

function renderEffects(ref) {
  const effects = document.createElement("section");
  effects.className = "tooltip-effects";

  const cooldown = document.createElement("div");
  cooldown.className = "tooltip-cooldown";
  const value = document.createElement("strong");
  value.textContent = formatValue(ref?.cooldown, "-");
  const unit = document.createElement("span");
  unit.textContent = "SEC";
  cooldown.append(value, unit);

  const lines = document.createElement("div");
  lines.className = "tooltip-lines";
  for (const line of ref?.effects ?? [ref?.tooltip ?? "Unknown item data for this patch."]) {
    const paragraph = document.createElement("p");
    paragraph.textContent = line;
    lines.append(paragraph);
  }

  effects.append(cooldown, lines);
  return effects;
}

function renderTooltip(itemState, anchor) {
  const ref = state.items.get(itemState.id);
  window.clearTimeout(state.hideTooltipTimer);
  refs.tooltip.hidden = false;
  refs.tooltip.innerHTML = "";

  const title = document.createElement("h2");
  title.textContent = ref?.name ?? titleCase(itemState.id);

  const typeRow = document.createElement("section");
  typeRow.className = "tooltip-row";
  const typeLabel = document.createElement("span");
  typeLabel.textContent = "TYPES";
  typeRow.append(typeLabel, renderPillList(ref?.types ?? [ref?.type ?? "Item"]));

  const text = document.createElement("section");
  text.className = "tooltip-text";
  text.textContent = ref?.tooltip ?? "Unknown item data for this patch.";

  const tagRow = document.createElement("section");
  tagRow.className = "tooltip-row";
  const tagLabel = document.createElement("span");
  tagLabel.textContent = "TAGS";
  tagRow.append(tagLabel, renderPillList(tagsFor(ref, itemState)));

  refs.tooltip.append(title, renderArt(ref), typeRow, renderEffects(ref), text, tagRow);
  positionTooltip(anchor);
}

function positionTooltip(anchor) {
  const tooltip = refs.tooltip;
  const rect = anchor.getBoundingClientRect();
  const width = Math.min(386, window.innerWidth - 16);
  const height = Math.min(620, window.innerHeight - 16);
  tooltip.style.width = `${width}px`;
  tooltip.style.maxHeight = `${height}px`;

  const preferRight = rect.left + rect.width / 2 < window.innerWidth / 2;
  const x = preferRight ? rect.right + 14 : rect.left - width - 14;
  const y = Math.min(
    Math.max(8, rect.top - 24),
    Math.max(8, window.innerHeight - height - 8),
  );

  tooltip.style.left = `${Math.max(8, Math.min(window.innerWidth - width - 8, x))}px`;
  tooltip.style.top = `${y}px`;
}

function hideTooltipSoon() {
  window.clearTimeout(state.hideTooltipTimer);
  state.hideTooltipTimer = window.setTimeout(() => {
    refs.tooltip.hidden = true;
  }, 180);
}

function renderSummary(payload) {
  refs.hero.textContent = titleCase(payload.hero ?? "Unknown hero");
  refs.day.textContent = formatValue(payload.day);
  refs.gold.textContent = formatValue(payload.gold);
  refs.health.textContent =
    payload.health === undefined
      ? "-"
      : `${payload.health}/${formatValue(payload.maxHealth, "?")}`;
  refs.phase.textContent = titleCase(payload.phase);
}

function fallbackBox(index) {
  return {
    x: 0.08 + index * 0.115,
    y: 0.58,
    w: 0.095,
    h: 0.17,
  };
}

function renderHotspots(payload) {
  refs.board.innerHTML = "";
  for (const [index, itemState] of (payload.board ?? []).entries()) {
    const box = itemState.bbox ?? fallbackBox(index);
    const ref = state.items.get(itemState.id);
    const button = document.createElement("button");
    button.className = "hotspot";
    button.type = "button";
    button.setAttribute("aria-label", ref?.name ?? titleCase(itemState.id));
    button.style.left = `${box.x * 100}%`;
    button.style.top = `${box.y * 100}%`;
    button.style.width = `${box.w * 100}%`;
    button.style.height = `${box.h * 100}%`;
    button.addEventListener("mouseenter", () => renderTooltip(itemState, button));
    button.addEventListener("focus", () => renderTooltip(itemState, button));
    button.addEventListener("mousemove", () => positionTooltip(button));
    button.addEventListener("mouseleave", hideTooltipSoon);
    button.addEventListener("blur", hideTooltipSoon);
    refs.board.append(button);
  }
}

function renderSnapshot(envelope) {
  const payload = envelope.payload;
  renderSummary(payload);
  renderHotspots(payload);
  setStatus(`Live seq ${envelope.seq}`);
}

function handleEnvelope(raw) {
  const parsed = parseEnvelope(raw);
  if (!parsed.ok) {
    setStatus(parsed.error);
    return;
  }

  const envelope = parsed.data;
  if (envelope.runId !== state.latestRunId) {
    state.latestRunId = envelope.runId;
    state.latestSeq = -1;
  }
  if (envelope.seq <= state.latestSeq) {
    return;
  }
  state.latestSeq = envelope.seq;
  state.latestEnvelope = envelope;

  if (envelope.type === "snapshot") {
    renderSnapshot(envelope);
  } else if (envelope.type === "heartbeat") {
    setStatus(envelope.payload.status);
  } else if (envelope.type === "reset") {
    refs.board.innerHTML = "";
    refs.tooltip.hidden = true;
    setStatus("Reset");
  }
}

async function loadDemoSnapshot() {
  const response = await fetch("./data/sample-snapshot.json");
  handleEnvelope(await response.json());
}

async function pollEbsLatest(baseUrl, channelId) {
  const response = await fetch(
    `${baseUrl}/v1/channels/${encodeURIComponent(channelId)}/latest`,
    { cache: "no-store" },
  );
  if (!response.ok) {
    setStatus(response.status === 404 ? "Waiting for EBS state" : "EBS error");
    return;
  }

  const latest = await response.json();
  handleEnvelope(latest.message);
}

function startLocalPolling(params) {
  const baseUrl = params.get("ebs")?.replace(/\/$/, "");
  if (!baseUrl) {
    return false;
  }

  const channelId = params.get("channel") ?? "dev-channel";
  const intervalMs = Number.parseInt(params.get("poll") ?? "1000", 10);
  const safeIntervalMs = Number.isFinite(intervalMs)
    ? Math.max(500, intervalMs)
    : 1000;

  setStatus("Polling EBS");
  pollEbsLatest(baseUrl, channelId).catch(() => setStatus("EBS unavailable"));
  state.localPollTimer = window.setInterval(() => {
    pollEbsLatest(baseUrl, channelId).catch(() => setStatus("EBS unavailable"));
  }, safeIntervalMs);
  return true;
}

function startHostedFallbackPolling(channelId) {
  if (state.localPollTimer || !channelId || window.location.protocol !== "https:") {
    return;
  }

  setStatus("Polling EBS fallback");
  const baseUrl = window.location.origin;
  pollEbsLatest(baseUrl, channelId).catch(() => setStatus("Waiting for live data"));
  state.localPollTimer = window.setInterval(() => {
    pollEbsLatest(baseUrl, channelId).catch(() => setStatus("Waiting for live data"));
  }, 1000);
}

function armHostedFallback() {
  window.setTimeout(() => {
    if (!state.latestEnvelope && state.twitchChannelId) {
      startHostedFallbackPolling(state.twitchChannelId);
    }
  }, 1500);
}

async function init() {
  await loadReferenceData();
  const params = new URLSearchParams(window.location.search);
  const localPolling = startLocalPolling(params);

  refs.tooltip.addEventListener("mouseenter", () => {
    window.clearTimeout(state.hideTooltipTimer);
  });
  refs.tooltip.addEventListener("mouseleave", hideTooltipSoon);

  if (!localPolling && window.Twitch?.ext?.listen) {
    window.Twitch.ext.listen("broadcast", (_target, _contentType, message) => {
      handleEnvelope(message);
    });
    window.Twitch.ext.onAuthorized((auth) => {
      state.twitchChannelId = auth.channelId;
      setStatus("Connected to Twitch");
      armHostedFallback();
    });
    window.Twitch.ext.onError(() => setStatus("Twitch helper error"));
  }

  if (!localPolling && (params.get("demo") === "1" || !window.Twitch?.ext?.listen)) {
    await loadDemoSnapshot();
  }
}

init().catch((error) => {
  setStatus(error instanceof Error ? error.message : "viewer_error");
});
