import { formatValue, titleCase } from "./protocol.js";

const TIER_OPTIONS = ["bronze", "silver", "gold", "diamond"];
const SETTINGS_KEY = "bazaar-companion-settings-v1";

const refs = {
  captureScreen: document.querySelector("#captureScreen"),
  publishNow: document.querySelector("#publishNow"),
  autoPublish: document.querySelector("#autoPublish"),
  ebsUrl: document.querySelector("#ebsUrl"),
  channelId: document.querySelector("#channelId"),
  token: document.querySelector("#token"),
  hero: document.querySelector("#hero"),
  phase: document.querySelector("#phase"),
  day: document.querySelector("#day"),
  gold: document.querySelector("#gold"),
  health: document.querySelector("#health"),
  maxHealth: document.querySelector("#maxHealth"),
  itemSearch: document.querySelector("#itemSearch"),
  searchResults: document.querySelector("#searchResults"),
  addSelected: document.querySelector("#addSelected"),
  boardEditor: document.querySelector("#boardEditor"),
  status: document.querySelector("#status"),
  stage: document.querySelector("#stage"),
  captureVideo: document.querySelector("#captureVideo"),
  captureEmpty: document.querySelector("#captureEmpty"),
  hotspots: document.querySelector("#hotspots"),
};

const state = {
  items: [],
  selectedItem: null,
  cards: [],
  selectedCardId: null,
  seq: 1,
  runId: `manual-${Date.now()}`,
  autoTimer: null,
};

function defaultEbsUrl() {
  return window.location.protocol === "https:"
    ? window.location.origin
    : "http://127.0.0.1:8000";
}

function loadSettings() {
  let settings = {};
  try {
    settings = JSON.parse(window.localStorage.getItem(SETTINGS_KEY) ?? "{}");
  } catch {
    settings = {};
  }

  refs.ebsUrl.value = settings.ebsUrl ?? defaultEbsUrl();
  refs.channelId.value = settings.channelId ?? "274185831";
  refs.token.value = settings.token ?? "";
  refs.hero.value = settings.hero ?? "vanessa";
  refs.phase.value = settings.phase ?? "combat";
  refs.day.value = settings.day ?? "7";
  refs.gold.value = settings.gold ?? "0";
  refs.health.value = settings.health ?? "100";
  refs.maxHealth.value = settings.maxHealth ?? "100";
}

function saveSettings() {
  const settings = {
    ebsUrl: refs.ebsUrl.value.trim(),
    channelId: refs.channelId.value.trim(),
    token: refs.token.value,
    hero: refs.hero.value.trim(),
    phase: refs.phase.value,
    day: refs.day.value,
    gold: refs.gold.value,
    health: refs.health.value,
    maxHealth: refs.maxHealth.value,
  };
  window.localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
}

function setStatus(message, data = null) {
  refs.status.textContent = data
    ? `${message}\n${JSON.stringify(data, null, 2)}`
    : message;
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

function itemSearchText(item) {
  return [
    item.id,
    item.name,
    item.cardId,
    item.bazaarDbId,
    ...(item.aliases ?? []),
    ...(item.types ?? []),
    ...(item.tags ?? []),
    ...(item.heroes ?? []),
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

function itemImage(item) {
  if (window.location.protocol === "https:" || !item.imageSource) {
    return item.image;
  }
  return item.imageSource;
}

async function loadItems() {
  const response = await fetch("./data/items.min.json");
  state.items = await response.json();
  state.selectedItem = state.items.find((item) => item.id === "dishwasher") ?? null;
  if (!refs.itemSearch.value && state.selectedItem) {
    refs.itemSearch.value = state.selectedItem.name;
  }
  renderSearchResults();
}

function renderSearchResults() {
  const query = refs.itemSearch.value.trim().toLowerCase();
  const normalizedQuery = normalizeItemId(query);
  const matches = state.items
    .filter((item) => {
      if (!query) return true;
      return (
        itemSearchText(item).includes(query) ||
        normalizeItemId(item.name).includes(normalizedQuery)
      );
    })
    .slice(0, 18);

  refs.searchResults.innerHTML = "";
  for (const item of matches) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "search-result";
    button.classList.toggle("active", item.id === state.selectedItem?.id);

    const image = document.createElement("span");
    image.className = "search-result-art";
    const art = itemImage(item);
    if (art) image.style.backgroundImage = `url("${art}")`;

    const text = document.createElement("span");
    text.className = "search-result-text";
    text.textContent = `${item.name} · ${titleCase(item.baseTier)} · ${(item.types ?? []).join(", ")}`;

    button.append(image, text);
    button.addEventListener("click", () => {
      state.selectedItem = item;
      renderSearchResults();
    });
    refs.searchResults.append(button);
  }
}

function defaultBox(index) {
  return {
    x: Math.min(0.82, 0.32 + (index % 5) * 0.095),
    y: 0.52,
    w: 0.085,
    h: 0.17,
  };
}

function addSelectedItem() {
  if (!state.selectedItem) {
    setStatus("Select an item first.");
    return;
  }

  const card = {
    localId:
      globalThis.crypto?.randomUUID?.() ?? `card-${Date.now()}-${state.cards.length}`,
    id: state.selectedItem.id,
    name: state.selectedItem.name,
    tier: state.selectedItem.baseTier || "bronze",
    cd: state.selectedItem.cooldown,
    ammo: state.selectedItem.ammo,
    bbox: defaultBox(state.cards.length),
  };
  state.cards.push(card);
  state.selectedCardId = card.localId;
  renderCards();
  setStatus(`Added ${card.name}.`);
}

function selectedCard() {
  return state.cards.find((card) => card.localId === state.selectedCardId) ?? null;
}

function numberOrNull(value) {
  if (value === "" || value === null || value === undefined) return null;
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function updateHotspotElement(card) {
  const element = refs.hotspots.querySelector(`[data-card-id="${card.localId}"]`);
  if (!element) return;
  element.style.left = `${card.bbox.x * 100}%`;
  element.style.top = `${card.bbox.y * 100}%`;
  element.style.width = `${card.bbox.w * 100}%`;
  element.style.height = `${card.bbox.h * 100}%`;
}

function startBoxDrag(event, card, mode) {
  event.preventDefault();
  event.stopPropagation();
  state.selectedCardId = card.localId;
  renderCards();

  const rect = refs.stage.getBoundingClientRect();
  const startX = event.clientX;
  const startY = event.clientY;
  const startBox = { ...card.bbox };

  const move = (moveEvent) => {
    const dx = (moveEvent.clientX - startX) / rect.width;
    const dy = (moveEvent.clientY - startY) / rect.height;

    if (mode === "resize") {
      card.bbox.w = clamp(startBox.w + dx, 0.025, 1 - startBox.x);
      card.bbox.h = clamp(startBox.h + dy, 0.045, 1 - startBox.y);
    } else {
      card.bbox.x = clamp(startBox.x + dx, 0, 1 - startBox.w);
      card.bbox.y = clamp(startBox.y + dy, 0, 1 - startBox.h);
    }
    updateHotspotElement(card);
  };

  const stop = () => {
    document.removeEventListener("pointermove", move);
    document.removeEventListener("pointerup", stop);
    renderCards();
  };

  document.addEventListener("pointermove", move);
  document.addEventListener("pointerup", stop);
}

function renderStageBoxes() {
  refs.hotspots.innerHTML = "";

  for (const card of state.cards) {
    const element = document.createElement("button");
    element.type = "button";
    element.className = "companion-hotspot";
    element.classList.toggle("active", card.localId === state.selectedCardId);
    element.dataset.cardId = card.localId;
    element.setAttribute("aria-label", card.name);

    const label = document.createElement("span");
    label.textContent = card.name;
    const handle = document.createElement("i");
    handle.setAttribute("aria-hidden", "true");

    element.append(label, handle);
    updateHotspotElement(card);
    element.addEventListener("pointerdown", (event) => startBoxDrag(event, card, "move"));
    handle.addEventListener("pointerdown", (event) => startBoxDrag(event, card, "resize"));
    refs.hotspots.append(element);
    updateHotspotElement(card);
  }
}

function renderBoardEditor() {
  refs.boardEditor.innerHTML = "";

  if (!state.cards.length) {
    const empty = document.createElement("p");
    empty.className = "board-empty";
    empty.textContent = "No cards.";
    refs.boardEditor.append(empty);
    return;
  }

  for (const card of state.cards) {
    const row = document.createElement("section");
    row.className = "board-row";
    row.classList.toggle("active", card.localId === state.selectedCardId);

    const name = document.createElement("button");
    name.type = "button";
    name.className = "board-row-name";
    name.textContent = card.name;
    name.addEventListener("click", () => {
      state.selectedCardId = card.localId;
      renderCards();
    });

    const tier = document.createElement("select");
    for (const option of TIER_OPTIONS) {
      const node = document.createElement("option");
      node.value = option;
      node.textContent = titleCase(option);
      tier.append(node);
    }
    tier.value = card.tier;
    tier.addEventListener("change", () => {
      card.tier = tier.value;
    });

    const cooldown = document.createElement("input");
    cooldown.type = "number";
    cooldown.min = "0";
    cooldown.step = "0.1";
    cooldown.value = card.cd ?? "";
    cooldown.placeholder = "CD";
    cooldown.addEventListener("change", () => {
      card.cd = numberOrNull(cooldown.value);
    });

    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "board-row-remove";
    remove.textContent = "Remove";
    remove.addEventListener("click", () => {
      state.cards = state.cards.filter((item) => item.localId !== card.localId);
      if (state.selectedCardId === card.localId) {
        state.selectedCardId = state.cards.at(-1)?.localId ?? null;
      }
      renderCards();
    });

    row.append(name, tier, cooldown, remove);
    refs.boardEditor.append(row);
  }
}

function renderCards() {
  renderStageBoxes();
  renderBoardEditor();
}

async function captureScreen() {
  if (!navigator.mediaDevices?.getDisplayMedia) {
    setStatus("Screen capture is unavailable in this browser.");
    return;
  }

  const stream = await navigator.mediaDevices.getDisplayMedia({
    video: {
      frameRate: 30,
      width: { ideal: 1920 },
      height: { ideal: 1080 },
    },
    audio: false,
  });
  refs.captureVideo.srcObject = stream;
  refs.captureEmpty.hidden = true;
  setStatus("Capture started.");

  const [track] = stream.getVideoTracks();
  track?.addEventListener("ended", () => {
    refs.captureEmpty.hidden = false;
    setStatus("Capture stopped.");
  });
}

function buildPayload() {
  return {
    hero: refs.hero.value.trim() || "vanessa",
    day: numberOrNull(refs.day.value),
    gold: numberOrNull(refs.gold.value),
    health: numberOrNull(refs.health.value),
    maxHealth: numberOrNull(refs.maxHealth.value),
    phase: refs.phase.value,
    board: state.cards.map((card, index) => ({
      slot: index,
      id: card.id,
      tier: card.tier,
      enchants: [],
      cd: card.cd,
      ammo: card.ammo,
      bbox: {
        x: Number(card.bbox.x.toFixed(4)),
        y: Number(card.bbox.y.toFixed(4)),
        w: Number(card.bbox.w.toFixed(4)),
        h: Number(card.bbox.h.toFixed(4)),
      },
    })),
    stash: [],
    skills: [],
  };
}

function buildEnvelope() {
  return {
    v: 1,
    type: "snapshot",
    seq: state.seq,
    sentAt: Date.now(),
    patch: "13.3",
    runId: state.runId,
    payload: buildPayload(),
  };
}

async function publishSnapshot() {
  saveSettings();
  const ebsUrl = refs.ebsUrl.value.trim().replace(/\/$/, "");
  const channelId = refs.channelId.value.trim();
  const token = refs.token.value;

  if (!ebsUrl || !channelId || !token) {
    setStatus("EBS URL, channel ID, and token are required.");
    return;
  }

  const envelope = buildEnvelope();
  const response = await fetch(
    `${ebsUrl}/v1/companion/${encodeURIComponent(channelId)}/snapshot`,
    {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(envelope),
    },
  );
  const body = await response.json().catch(() => ({}));
  if (!response.ok) {
    setStatus(`Publish failed: ${response.status}`, body);
    return;
  }

  state.seq += 1;
  setStatus(
    `Published seq ${envelope.seq}: ${state.cards.length} cards, ${formatValue(body.sizeBytes)} bytes.`,
    body,
  );
}

function setAutoPublish(enabled) {
  window.clearInterval(state.autoTimer);
  state.autoTimer = null;

  if (!enabled) return;
  state.autoTimer = window.setInterval(() => {
    publishSnapshot().catch((error) => {
      setStatus(error instanceof Error ? error.message : "Publish failed.");
    });
  }, 1300);
  publishSnapshot().catch((error) => {
    setStatus(error instanceof Error ? error.message : "Publish failed.");
  });
}

function bindInputs() {
  for (const input of [
    refs.ebsUrl,
    refs.channelId,
    refs.token,
    refs.hero,
    refs.phase,
    refs.day,
    refs.gold,
    refs.health,
    refs.maxHealth,
  ]) {
    input.addEventListener("change", saveSettings);
  }

  refs.itemSearch.addEventListener("input", renderSearchResults);
  refs.addSelected.addEventListener("click", addSelectedItem);
  refs.captureScreen.addEventListener("click", () => {
    captureScreen().catch((error) => {
      setStatus(error instanceof Error ? error.message : "Capture failed.");
    });
  });
  refs.publishNow.addEventListener("click", () => {
    publishSnapshot().catch((error) => {
      setStatus(error instanceof Error ? error.message : "Publish failed.");
    });
  });
  refs.autoPublish.addEventListener("change", () => {
    setAutoPublish(refs.autoPublish.checked);
  });
}

async function init() {
  loadSettings();
  bindInputs();
  await loadItems();
  renderCards();
}

init().catch((error) => {
  setStatus(error instanceof Error ? error.message : "companion_error");
});
