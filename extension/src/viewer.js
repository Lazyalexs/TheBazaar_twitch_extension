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

  const closeBtn = document.createElement("button");
  closeBtn.className = "tooltip-close";
  closeBtn.setAttribute("aria-label", "Close");
  closeBtn.textContent = "\u00d7";
  closeBtn.addEventListener("click", (e) => {
    e.stopPropagation();
    refs.tooltip.hidden = true;
    refs.tooltip.innerHTML = "";
  });
  refs.tooltip.append(closeBtn);
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
  const poll = () => {
    pollEbsLatest(baseUrl, channelId).catch(() => setStatus("EBS unavailable"));
  };
  poll();

  const startTimer = () => {
    if (state.localPollTimer !== null) return;
    state.localPollTimer = window.setInterval(poll, safeIntervalMs);
  };
  const stopTimer = () => {
    if (state.localPollTimer !== null) {
      clearInterval(state.localPollTimer);
      state.localPollTimer = null;
    }
  };
  startTimer();

  window.addEventListener("beforeunload", stopTimer);
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "hidden") {
      stopTimer();
    } else {
      poll();
      startTimer();
    }
  });

  return true;
}

async function init() {
  await loadReferenceData();
  const params = new URLSearchParams(window.location.search);
  const localPolling = startLocalPolling(params);

  if (!localPolling && window.Twitch?.ext?.listen) {
    window.Twitch.ext.listen("broadcast", (_target, _contentType, message) => {
      handleEnvelope(message);
    });
    window.Twitch.ext.onAuthorized(() => setStatus("Connected to Twitch"));
    window.Twitch.ext.onError(() => setStatus("Twitch helper error"));
  }

  if (!localPolling && (params.get("demo") === "1" || !window.Twitch?.ext?.listen)) {
    await loadDemoSnapshot();
  }

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !refs.tooltip.hidden) {
      refs.tooltip.hidden = true;
      refs.tooltip.innerHTML = "";
    }
  });
  document.addEventListener("click", (e) => {
    if (refs.tooltip.hidden) return;
    if (!refs.tooltip.contains(e.target) && !e.target.closest(".item")) {
      refs.tooltip.hidden = true;
      refs.tooltip.innerHTML = "";
    }
  });

  if (!localPolling && state.latestEnvelope === null) {
    setStatus("Open with ?demo=1 to see sample data, or ?ebs=<url>&channel=<id> to poll your local EBS.");
  }
}

init().catch((error) => {
  setStatus(error instanceof Error ? error.message : "viewer_error");
});