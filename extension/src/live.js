const refs = {
  ebsUrl: document.querySelector("#ebsUrl"),
  channelId: document.querySelector("#channelId"),
  checkHealth: document.querySelector("#checkHealth"),
  diagnostics: document.querySelector("#diagnostics"),
};

const state = {
  twitchToken: null,
  channelId: null,
};

function defaultEbsUrl() {
  if (window.location.protocol === "https:") {
    return window.location.origin;
  }
  return "http://127.0.0.1:8000";
}

function write(value) {
  refs.diagnostics.textContent =
    typeof value === "string" ? value : JSON.stringify(value, null, 2);
}

async function checkHealth() {
  localStorage.setItem("bazaar.ebsUrl", refs.ebsUrl.value);
  localStorage.setItem("bazaar.channelId", refs.channelId.value);

  const baseUrl = refs.ebsUrl.value.replace(/\/$/, "");
  const health = await fetch(`${baseUrl}/health`);
  const healthJson = await health.json();

  let latest = null;
  try {
    const latestResponse = await fetch(
      `${baseUrl}/v1/channels/${refs.channelId.value}/latest`,
    );
    latest = latestResponse.ok ? await latestResponse.json() : await latestResponse.text();
  } catch (error) {
    latest = error instanceof Error ? error.message : String(error);
  }

  write({ health: healthJson, latest });
}

refs.ebsUrl.value = localStorage.getItem("bazaar.ebsUrl") ?? defaultEbsUrl();
refs.channelId.value =
  localStorage.getItem("bazaar.channelId") ?? refs.channelId.value;
refs.checkHealth.addEventListener("click", () => {
  checkHealth().catch((error) => write(error instanceof Error ? error.message : error));
});

if (window.Twitch?.ext?.onAuthorized) {
  window.Twitch.ext.onAuthorized((auth) => {
    state.twitchToken = auth.token;
    state.channelId = auth.channelId;
    if (auth.channelId) {
      refs.channelId.value = auth.channelId;
      localStorage.setItem("bazaar.channelId", auth.channelId);
    }
    write({ twitchAuthorized: true, channelId: auth.channelId });
  });
}
