#!/usr/bin/env node

import { mkdir, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { setTimeout as delay } from "node:timers/promises";
import https from "node:https";

const DEFAULT_HOST = "https://sin.bazaardb.gg";
const TIER_ORDER = ["Bronze", "Silver", "Gold", "Diamond", "Legendary"];

function parseArgs(argv) {
  const args = {
    host: DEFAULT_HOST,
    out: "extension/data/items.min.json",
    manifest: "extension/data/manifest.json",
    category: "items",
    delayMs: 80,
    page: null,
  };

  for (let index = 0; index < argv.length; index += 1) {
    const arg = argv[index];
    const next = () => argv[++index];
    if (arg === "--host") args.host = next();
    else if (arg === "--out") args.out = next();
    else if (arg === "--manifest") args.manifest = next();
    else if (arg === "--category") args.category = next();
    else if (arg === "--delay-ms") args.delayMs = Number.parseInt(next(), 10);
    else if (arg === "--page") args.page = Number.parseInt(next(), 10);
    else if (arg === "--help" || arg === "-h") {
      console.log(
        [
          "Usage: node tools/sync-bazaardb-data.mjs [options]",
          "",
          "Options:",
          "  --host <url>        BazaarDB mirror to read (default: https://sin.bazaardb.gg)",
          "  --out <path>        Output JSON path (default: extension/data/items.min.json)",
          "  --manifest <path>   Manifest JSON path (default: extension/data/manifest.json)",
          "  --delay-ms <ms>     Delay between page requests (default: 80)",
          "  --page <n>          Sync only one BazaarDB page, useful for debugging",
        ].join("\n"),
      );
      process.exit(0);
    } else {
      throw new Error(`Unknown argument: ${arg}`);
    }
  }
  return args;
}

function fetchText(url, attempts = 3) {
  return new Promise((resolvePromise, rejectPromise) => {
    const request = https.get(
      url,
      {
        family: 4,
        headers: {
          "User-Agent": "TheBazaarTwitchExtensionDataSync/0.1",
          Accept: "text/html,application/xhtml+xml",
        },
        timeout: 30_000,
      },
      (response) => {
        let body = "";
        response.setEncoding("utf8");
        response.on("data", (chunk) => {
          body += chunk;
        });
        response.on("end", async () => {
          if (response.statusCode >= 500 && attempts > 1) {
            await delay(500);
            fetchText(url, attempts - 1).then(resolvePromise, rejectPromise);
            return;
          }
          if (response.statusCode < 200 || response.statusCode >= 300) {
            rejectPromise(
              new Error(`GET ${url} failed with HTTP ${response.statusCode}`),
            );
            return;
          }
          resolvePromise(body);
        });
      },
    );

    request.on("timeout", () => {
      request.destroy(new Error(`GET ${url} timed out`));
    });
    request.on("error", async (error) => {
      if (attempts > 1) {
        await delay(500);
        fetchText(url, attempts - 1).then(resolvePromise, rejectPromise);
        return;
      }
      rejectPromise(error);
    });
  });
}

function extractJsonObject(source, start) {
  let depth = 0;
  let inString = false;
  let escaped = false;

  for (let index = start; index < source.length; index += 1) {
    const char = source[index];
    if (inString) {
      if (escaped) escaped = false;
      else if (char === "\\") escaped = true;
      else if (char === '"') inString = false;
      continue;
    }

    if (char === '"') {
      inString = true;
      continue;
    }
    if (char === "{") depth += 1;
    else if (char === "}") {
      depth -= 1;
      if (depth === 0) {
        return source.slice(start, index + 1);
      }
    }
  }
  throw new Error("Could not find the end of the initialData object");
}

function decodeNextFlight(html) {
  const chunks = [];
  const chunkPattern = /self\.__next_f\.push\(\[1,"((?:\\.|[^"\\])*)"\]\)<\/script>/g;
  for (const match of html.matchAll(chunkPattern)) {
    chunks.push(JSON.parse(`"${match[1]}"`));
  }
  return chunks.join("");
}

function extractInitialData(html) {
  const unescaped = decodeNextFlight(html) || html;
  const marker = '"initialData":';
  const markerIndex = unescaped.indexOf(marker);
  if (markerIndex === -1) {
    throw new Error("Could not find BazaarDB initialData in the page HTML");
  }
  const start = markerIndex + marker.length;
  const initialData = JSON.parse(extractJsonObject(unescaped, start));
  initialData.latestVersion =
    initialData.latestVersion ??
    unescaped.match(/"latestVersion":"([^"]+)"/)?.[1] ??
    "unknown";
  return initialData;
}

function slugify(value) {
  return String(value)
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/&/g, " and ")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "_")
    .replace(/^_+|_+$/g, "");
}

function normalizeTier(value) {
  return String(value ?? "").toLowerCase();
}

function formatNumber(value) {
  if (typeof value !== "number") return String(value ?? "");
  if (Number.isInteger(value)) return String(value);
  return String(Number(value.toFixed(2))).replace(/\.0+$/, "");
}

function replacementValues(replacement) {
  if (!replacement || typeof replacement !== "object") return [];
  if (Object.hasOwn(replacement, "Fixed")) return [replacement.Fixed];
  return TIER_ORDER.filter((tier) => Object.hasOwn(replacement, tier)).map(
    (tier) => replacement[tier],
  );
}

function renderReplacement(text, token, replacement) {
  const values = replacementValues(replacement);
  if (!values.length) return text;

  const plain = values.map(formatNumber).join(" » ");
  const plus = values.map((value) => `+${formatNumber(value)}`).join(" » ");
  const percent = values.map((value) => `${formatNumber(value)}%`).join(" » ");
  const plusPercent = values
    .map((value) => `+${formatNumber(value)}%`)
    .join(" » ");

  return text
    .replaceAll(`+${token}%`, plusPercent)
    .replaceAll(`${token}%`, percent)
    .replaceAll(`+${token}`, plus)
    .replaceAll(token, plain);
}

function renderTooltipText(text, replacements = {}) {
  let rendered = text ?? "";
  for (const [token, replacement] of Object.entries(replacements)) {
    rendered = renderReplacement(rendered, token, replacement);
  }
  return rendered
    .replace(/\{[^}]+}/g, "?")
    .replace(/\s+/g, " ")
    .replace(/\s+([.,:;!?])/g, "$1")
    .trim();
}

function activeTooltipIds(card) {
  const baseTier = card.Tiers?.[card.BaseTier] ?? Object.values(card.Tiers ?? {})[0];
  const ids = baseTier?.ActiveTooltips;
  if (Array.isArray(ids) && ids.length) return ids;
  return (card.Tooltips ?? []).map((_tooltip, index) => index);
}

function cardEffects(card) {
  return activeTooltipIds(card)
    .map((id) => card.Tooltips?.[id]?.Content?.Text)
    .filter(Boolean)
    .map((text) => renderTooltipText(text, card.TooltipReplacements))
    .filter(Boolean);
}

function numericAttribute(card, key) {
  const value = card.BaseAttributes?.[key];
  return typeof value === "number" ? value : null;
}

function secondsFromMs(ms) {
  return typeof ms === "number" && ms > 0 ? Number((ms / 1000).toFixed(2)) : null;
}

function proxiedArtUrl(url) {
  if (!url) return null;
  try {
    const parsed = new URL(url);
    if (parsed.hostname === "s.bazaardb.gg" || parsed.hostname === "i.bazaardb.gg") {
      return `/bazaar-art/${parsed.hostname}${parsed.pathname}${parsed.search}`;
    }
  } catch {
    return url;
  }
  return url;
}

function mapCard(card) {
  const name = card.Title?.Text ?? card._originalTitleText ?? "Unknown";
  const id = slugify(name);
  const uriParts = String(card.Uri ?? "").split("/").filter(Boolean);
  const urlId = uriParts[1] ?? null;
  const description = card.Description?.Text
    ? renderTooltipText(card.Description.Text, card.TooltipReplacements)
    : "";

  return {
    id,
    aliases: [card.Id, urlId, name, card._originalTitleText]
      .filter(Boolean)
      .map(String),
    cardId: card.Id,
    bazaarDbId: urlId,
    name,
    type: String(card.Type ?? "Item").toLowerCase(),
    types: card.DisplayTags ?? [],
    heroes: (card.Heroes ?? []).map((hero) => String(hero).toLowerCase()),
    size: normalizeTier(card.Size),
    baseTier: normalizeTier(card.BaseTier),
    tags: card.Tags ?? [],
    hiddenTags: card.HiddenTags ?? [],
    cooldown: secondsFromMs(numericAttribute(card, "CooldownMax")),
    ammo: numericAttribute(card, "AmmoMax"),
    multicast: numericAttribute(card, "Multicast"),
    cost: numericAttribute(card, "BuyPrice"),
    value: numericAttribute(card, "SellPrice"),
    effects: cardEffects(card),
    tooltip: description,
    image: proxiedArtUrl(card.Art),
    imageSource: card.Art ?? null,
    bazaarDbUrl: card.Uri ? `https://bazaardb.gg${card.Uri}` : null,
    enchantments: Object.keys(card.Enchantments ?? {}),
  };
}

function pageUrl(host, category, page) {
  const url = new URL("/search", host);
  url.searchParams.set("c", category);
  url.searchParams.set("page", String(page));
  return url.toString();
}

async function readPage(host, category, page) {
  const html = await fetchText(pageUrl(host, category, page));
  return extractInitialData(html);
}

async function sync() {
  const args = parseArgs(process.argv.slice(2));
  const firstPage = args.page ?? 1;
  const initialData = await readPage(args.host, args.category, firstPage);
  const total = initialData.total ?? initialData.pageCards?.length ?? 0;
  const pageSize = initialData.pageCards?.length ?? 10;
  const pageCount = args.page ? 1 : Math.ceil(total / pageSize);
  const cardsById = new Map();

  const addCards = (cards) => {
    for (const card of cards ?? []) {
      if (card.Type === "Item") {
        cardsById.set(card.Id, card);
      }
    }
  };

  addCards(initialData.pageCards);
  console.log(`Read BazaarDB page ${firstPage}/${pageCount} (${cardsById.size}/${total})`);

  for (let page = 2; page <= pageCount; page += 1) {
    await delay(args.delayMs);
    const data = await readPage(args.host, args.category, page);
    addCards(data.pageCards);
    console.log(`Read BazaarDB page ${page}/${pageCount} (${cardsById.size}/${total})`);
  }

  const items = [...cardsById.values()]
    .map(mapCard)
    .sort((left, right) => left.name.localeCompare(right.name, "en"));

  const outPath = resolve(args.out);
  const manifestPath = resolve(args.manifest);
  await mkdir(dirname(outPath), { recursive: true });
  await mkdir(dirname(manifestPath), { recursive: true });
  await writeFile(outPath, `${JSON.stringify(items)}\n`, "utf8");
  await writeFile(
    manifestPath,
    `${JSON.stringify(
      {
        source: "BazaarDB",
        sourceHost: args.host,
        canonicalHost: "https://bazaardb.gg",
        category: args.category,
        latestVersion: initialData.latestVersion ?? "unknown",
        total: items.length,
        syncedAt: new Date().toISOString(),
      },
      null,
      2,
    )}\n`,
    "utf8",
  );

  console.log(`Wrote ${items.length} items to ${outPath}`);
}

sync().catch((error) => {
  console.error(error instanceof Error ? error.stack : error);
  process.exit(1);
});
