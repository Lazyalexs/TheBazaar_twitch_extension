export function parseEnvelope(raw) {
  let data;
  try {
    data = typeof raw === "string" ? JSON.parse(raw) : raw;
  } catch {
    return { ok: false, error: "invalid_json" };
  }

  if (!data || data.v !== 1 || typeof data.type !== "string") {
    return { ok: false, error: "invalid_envelope" };
  }

  if (!Number.isFinite(data.seq) || !Number.isFinite(data.sentAt)) {
    return { ok: false, error: "invalid_sequence" };
  }

  if (!data.payload || typeof data.payload !== "object") {
    return { ok: false, error: "invalid_payload" };
  }

  return { ok: true, data };
}

export function formatValue(value, fallback = "-") {
  if (value === null || value === undefined || value === "") {
    return fallback;
  }
  return String(value);
}

export function titleCase(value) {
  return formatValue(value)
    .replaceAll("_", " ")
    .replace(/\b\w/g, (letter) => letter.toUpperCase());
}

