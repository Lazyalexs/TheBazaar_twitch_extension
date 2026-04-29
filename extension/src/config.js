const refs = {
  ebsUrl: document.querySelector("#ebsUrl"),
  saveConfig: document.querySelector("#saveConfig"),
  verifySetup: document.querySelector("#verifySetup"),
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

refs.ebsUrl.value = localStorage.getItem("bazaar.ebsUrl") ?? defaultEbsUrl();

refs.saveConfig.addEventListener("click", () => {
  localStorage.setItem("bazaar.ebsUrl", refs.ebsUrl.value);
  write(`Saved ${refs.ebsUrl.value}`);
});

refs.verifySetup.addEventListener("click", async () => {
  if (!state.twitchToken) {
    write("Twitch authorization is not available in this context.");
    return;
  }

  const baseUrl = refs.ebsUrl.value.replace(/\/$/, "");
  const response = await fetch(`${baseUrl}/v1/extension/setup`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${state.twitchToken}`,
    },
  });
  const body = await response.json().catch(() => null);
  write({
    ok: response.ok,
    status: response.status,
    channelId: state.channelId,
    body,
  });
});

if (window.Twitch?.ext?.onAuthorized) {
  window.Twitch.ext.onAuthorized((auth) => {
    state.twitchToken = auth.token;
    state.channelId = auth.channelId;
    write({ twitchAuthorized: true, channelId: auth.channelId });
  });
}
