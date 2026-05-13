import { formatValue, parseEnvelope, titleCase } from "./protocol.js";

const MIN_ITEM_CONFIDENCE = 0.98;
const UNKNOWN_ITEM_PREFIX = "unknown:";

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
  debugUi: false,
};

async function loadReferenceData() {
  const response = await fetch("./data/items.min.json");
  const items = await response.json();
  state.items = new Map();
  for (const item of items) {
    for (const key of [item.id, item.cardId, item.bazaarDbId, item.name, ...(item.aliases ?? [])]) {
      const normalized = normalizeItemId(key);
      if (normalized) {
        state.items.set(normalized, item);
      }
    }
  }
}

function setStatus(text) {
  refs.status.textContent = text;
}

function tierLabel(value) {
  return value ? `${titleCase(value)}+` : "Item";
}

function normalizeItemId(value) {
  return String(value ?? "")
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/&/g, " and ")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function itemRef(id) {
  return state.items.get(normalizeItemId(id));
}

function isUnknownItem(itemState) {
  return String(itemState?.id ?? "").toLowerCase().startsWith(UNKNOWN_ITEM_PREFIX);
}

function itemName(ref, itemState) {
  if (ref?.name) {
    return ref.name;
  }
  return isUnknownItem(itemState) ? "Unknown item" : String(itemState?.id ?? "Unknown item");
}

function validBox(box) {
  return Boolean(
    box &&
      Number.isFinite(box.x) &&
      Number.isFinite(box.y) &&
      Number.isFinite(box.w) &&
      Number.isFinite(box.h) &&
      box.x >= 0 &&
      box.y >= 0 &&
      box.w > 0 &&
      box.h > 0 &&
      box.x + box.w <= 1 &&
      box.y + box.h <= 1,
  );
}

function validItemConfidence(itemState) {
  return (itemState.confidence ?? 1) >= MIN_ITEM_CONFIDENCE;
}

function uniqueLabels(items) {
  const seen = new Set();
  const labels = [];
  for (const item of items) {
    const value = String(item ?? "").trim();
    const key = value.toLowerCase();
    if (value && !seen.has(key)) {
      seen.add(key);
      labels.push(value);
    }
  }
  return labels;
}

function tagsFor(ref, itemState) {
  const tags = [
    tierLabel(itemState.tier ?? ref?.baseTier),
    ...(ref?.tags ?? []),
  ];
  return uniqueLabels(tags);
}

function renderArt(ref) {
  const art = document.createElement("div");
  art.className = "tooltip-art";
  const image =
    window.location.protocol === "https:" || !ref?.imageSource
      ? ref?.image
      : ref?.imageSource;
  if (image) {
    art.style.backgroundImage = `url("${image}")`;
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

function renderEffects(ref, itemState) {
  const effects = document.createElement("section");
  effects.className = "tooltip-effects";

  const cooldown = document.createElement("div");
  cooldown.className = "tooltip-cooldown";
  const value = document.createElement("strong");
  value.textContent = formatValue(itemState.cd ?? ref?.cooldown, "-");
  const unit = document.createElement("span");
  unit.textContent = "SEC";
  cooldown.append(value, unit);

  const lines = document.createElement("div");
  lines.className = "tooltip-lines";
  const effectLines =
    ref?.effects?.length
      ? ref.effects
      : [
          ref?.tooltip ??
            (isUnknownItem(itemState)
              ? "Waiting for game template data."
              : "Unknown item data for this patch."),
        ];
  for (const line of effectLines) {
    const paragraph = document.createElement("p");
    paragraph.textContent = line;
    lines.append(paragraph);
  }

  effects.append(cooldown, lines);
  return effects;
}

function renderTooltip(itemState, anchor) {
  const ref = itemRef(itemState.id);
  window.clearTimeout(state.hideTooltipTimer);
  refs.tooltip.hidden = false;
  refs.tooltip.innerHTML = "";

  const title = document.createElement("h2");
  title.textContent = itemName(ref, itemState);

  const typeRow = document.createElement("section");
  typeRow.className = "tooltip-row";
  const typeLabel = document.createElement("span");
  typeLabel.textContent = "TYPES";
  const types = ref?.types?.length ? ref.types : [ref?.type ?? "Item"];
  typeRow.append(typeLabel, renderPillList(types));

  const tagRow = document.createElement("section");
  tagRow.className = "tooltip-row";
  const tagLabel = document.createElement("span");
  tagLabel.textContent = "TAGS";
  tagRow.append(tagLabel, renderPillList(tagsFor(ref, itemState)));

  refs.tooltip.append(title, renderArt(ref), typeRow, renderEffects(ref, itemState));
  if (ref?.tooltip) {
    const text = document.createElement("section");
    text.className = "tooltip-text";
    text.textContent = ref.tooltip;
    refs.tooltip.append(text);
  }
  refs.tooltip.append(tagRow);
  positionTooltip(anchor);
}

function positionTooltip(anchor) {
  const tooltip = refs.tooltip;
  const rect = anchor.getBoundingClientRect();
  const width = Math.round(
    Math.min(213, Math.max(160, window.innerWidth * 0.187), window.innerWidth - 16),
  );
  const height = Math.round(
    Math.min(287, Math.max(173, window.innerHeight * 0.52), window.innerHeight - 16),
  );
  tooltip.style.width = `${width}px`;
  tooltip.style.maxHeight = `${height}px`;

  const gap = 12;
  const roomRight = window.innerWidth - rect.right;
  const roomLeft = rect.left;
  const preferRight = roomRight >= width + gap || roomRight >= roomLeft;
  const sideX = preferRight ? rect.right + gap : rect.left - width - gap;
  const centerY = rect.top + rect.height / 2 - height / 2;
  const y = Math.min(
    Math.max(8, centerY),
    Math.max(8, window.innerHeight - height - 8),
  );

  tooltip.style.left =
    `${Math.max(8, Math.min(window.innerWidth - width - 8, sideX))}px`;
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

function renderHotspots(payload) {
  refs.board.innerHTML = "";
  refs.board.classList.toggle(
    "debug-hotspots",
    state.debugUi || payload.debugHotspots === true,
  );
  const hotspotItems = [
    ...(payload.opponentBoard ?? []).map((item) => ({ item, side: "opponent" })),
    ...(payload.board ?? []).map((item) => ({ item, side: "player" })),
  ];
  for (const { item: itemState, side } of hotspotItems) {
    const ref = itemRef(itemState.id);
    const box = itemState.bbox;
    if (
      (!ref && !isUnknownItem(itemState)) ||
      !validBox(box) ||
      !validItemConfidence(itemState)
    ) {
      continue;
    }

    const name = itemName(ref, itemState);
    const button = document.createElement("button");
    button.className = `hotspot ${side}-hotspot`;
    button.type = "button";
    button.setAttribute("aria-label", name);
    button.style.left = `${box.x * 100}%`;
    button.style.top = `${box.y * 100}%`;
    button.style.width = `${box.w * 100}%`;
    button.style.height = `${box.h * 100}%`;
    const label = document.createElement("span");
    label.textContent = name;
    button.append(label);
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
  if (params.get("debug") === "1") {
    state.debugUi = true;
    document.body.classList.add("debug-ui");
  }
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
