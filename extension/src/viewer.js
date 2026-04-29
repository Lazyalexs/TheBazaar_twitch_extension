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
};

async function loadReferenceData() {
  const response = await fetch("./data/items.min.json");
  const items = await response.json();
  state.items = new Map(items.map((item) => [item.id, item]));
}

function setStatus(text) {
  refs.status.textContent = text;
}

function renderTooltip(itemState) {
  const ref = state.items.get(itemState.id);
  refs.tooltip.hidden = false;
  refs.tooltip.innerHTML = "";

  const title = document.createElement("h2");
  title.textContent = ref?.name ?? titleCase(itemState.id);
  const copy = document.createElement("p");
  copy.textContent = ref?.tooltip ?? "Unknown item data for this patch.";

  refs.tooltip.append(title, copy);
}

function renderSnapshot(envelope) {
  const payload = envelope.payload;
  refs.hero.textContent = titleCase(payload.hero ?? "Unknown hero");
  refs.day.textContent = formatValue(payload.day);
  refs.gold.textContent = formatValue(payload.gold);
  refs.health.textContent =
    payload.health === undefined
      ? "-"
      : `${payload.health}/${formatValue(payload.maxHealth, "?")}`;
  refs.phase.textContent = titleCase(payload.phase);

  refs.board.innerHTML = "";
  for (const itemState of payload.board ?? []) {
    const ref = state.items.get(itemState.id);
    const button = document.createElement("button");
    button.className = "item";
    button.type = "button";
    button.addEventListener("click", () => renderTooltip(itemState));

    const tier = document.createElement("span");
    tier.textContent = itemState.tier ?? "item";
    const name = document.createElement("strong");
    name.textContent = ref?.name ?? titleCase(itemState.id);
    button.append(tier, name);
    refs.board.append(button);
  }

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
