import { execFileSync } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";

const CHAIN = "solana";
const OUT_FILE = "docs/data/meme.json";

function runOnchainos(args) {
  const output = execFileSync("onchainos", args, {
    encoding: "utf8",
    maxBuffer: 20 * 1024 * 1024
  });

  const parsed = JSON.parse(output);
  if (!parsed.ok) {
    throw new Error(`onchainos ${args.join(" ")} returned ok=false`);
  }
  return Array.isArray(parsed.data) ? parsed.data : [];
}

function toNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function toIso(ms) {
  const value = Number(ms);
  if (!Number.isFinite(value) || value <= 0) {
    return "";
  }
  return new Date(value).toISOString();
}

function shortAddress(address) {
  if (!address) {
    return "";
  }
  if (address.length <= 12) {
    return address;
  }
  return `${address.slice(0, 4)}...${address.slice(-4)}`;
}

function protocolName(protocolId) {
  const names = {
    "120596": "pumpfun",
    "136266": "bonk",
    "139661": "bonkers",
    "137346": "jupStudio",
    "134788": "believe",
    "129813": "bags",
    "133933": "moonshotMoney",
    "136137": "launchlab",
    "121201": "moonshot",
    "136460": "meteoradbc",
    "139048": "mayhem"
  };
  return names[protocolId] ?? protocolId ?? "";
}

function riskHint(token) {
  const top10 = toNumber(token.tags?.top10HoldingsPercent);
  const snipers = toNumber(token.tags?.snipersPercent);
  const bundlers = toNumber(token.tags?.bundlersPercent);
  const dev = toNumber(token.tags?.devHoldingsPercent);
  const phishing = toNumber(token.tags?.suspectedPhishingWalletPercent);

  if (top10 >= 50 || snipers >= 50 || dev >= 20) {
    return "高风险";
  }
  if (phishing >= 5 || bundlers >= 10 || top10 >= 25 || snipers >= 25) {
    return "需复查";
  }
  return "观察";
}

function actionHint(token, group) {
  const risk = riskHint(token);
  const volume = toNumber(token.market?.volumeUsd1h);
  const top10 = toNumber(token.tags?.top10HoldingsPercent);
  const bonding = toNumber(token.bondingPercent);

  if (risk === "高风险") {
    return "跳过";
  }
  if (group === "graduated" && volume >= 50000 && top10 < 30) {
    return "重点看承接";
  }
  if (group === "ungraduated" && bonding >= 85 && volume >= 10000 && top10 < 35) {
    return "临近毕业观察";
  }
  return "观察";
}

function normalize(token, group, stage, stageLabel) {
  return {
    name: token.name || "(未命名)",
    symbol: token.symbol || "",
    address: token.tokenAddress || "",
    shortAddress: shortAddress(token.tokenAddress),
    chain: "Solana",
    chainIndex: token.chainIndex || "501",
    protocolId: token.protocolId || "",
    protocol: protocolName(token.protocolId),
    stage,
    stageLabel,
    group,
    createdTimestamp: toNumber(token.createdTimestamp),
    createdAt: toIso(token.createdTimestamp),
    migratedBeginTimestamp: toNumber(token.migratedBeginTimestamp),
    migratedBeginAt: toIso(token.migratedBeginTimestamp),
    migratedEndTimestamp: toNumber(token.migratedEndTimestamp),
    migratedEndAt: toIso(token.migratedEndTimestamp),
    bondingPercent: toNumber(token.bondingPercent),
    marketCapUsd: toNumber(token.market?.marketCapUsd),
    volumeUsd1h: toNumber(token.market?.volumeUsd1h),
    txCount1h: toNumber(token.market?.txCount1h),
    buyTxCount1h: toNumber(token.market?.buyTxCount1h),
    sellTxCount1h: toNumber(token.market?.sellTxCount1h),
    holders: toNumber(token.tags?.totalHolders),
    top10HoldingsPercent: toNumber(token.tags?.top10HoldingsPercent),
    devHoldingsPercent: toNumber(token.tags?.devHoldingsPercent),
    bundlersPercent: toNumber(token.tags?.bundlersPercent),
    snipersPercent: toNumber(token.tags?.snipersPercent),
    freshWalletsPercent: toNumber(token.tags?.freshWalletsPercent),
    insidersPercent: toNumber(token.tags?.insidersPercent),
    suspectedPhishingWalletPercent: toNumber(token.tags?.suspectedPhishingWalletPercent),
    aped: toNumber(token.aped),
    creatorAddress: token.creatorAddress || "",
    quoteTokenAddress: token.quoteTokenAddress || "",
    social: {
      website: token.social?.website || "",
      x: token.social?.x || "",
      telegram: token.social?.telegram || "",
      communityTakeover: Boolean(token.social?.communityTakeover),
      dexScreenerPaid: Boolean(token.social?.dexScreenerPaid),
      liveOnPumpFun: Boolean(token.social?.liveOnPumpFun)
    },
    bagsFeeClaimed: Boolean(token.bagsFeeClaimed),
    riskHint: riskHint(token),
    actionHint: actionHint(token, group)
  };
}

function uniqueByAddress(items) {
  const byAddress = new Map();
  for (const item of items) {
    if (!item.address) {
      continue;
    }
    const existing = byAddress.get(item.address);
    if (!existing || item.bondingPercent > existing.bondingPercent) {
      byAddress.set(item.address, item);
    }
  }
  return [...byAddress.values()];
}

const newTokens = runOnchainos(["memepump", "tokens", "--chain", CHAIN, "--stage", "NEW"])
  .map((token) => normalize(token, "ungraduated", "NEW", "新创建"));
const migratingTokens = runOnchainos(["memepump", "tokens", "--chain", CHAIN, "--stage", "MIGRATING"])
  .map((token) => normalize(token, "ungraduated", "MIGRATING", "迁移中"));
const migratedTokens = runOnchainos(["memepump", "tokens", "--chain", CHAIN, "--stage", "MIGRATED"])
  .map((token) => normalize(token, "graduated", "MIGRATED", "刚毕业"));

const ungraduated = uniqueByAddress([...newTokens, ...migratingTokens])
  .sort((a, b) => (b.bondingPercent - a.bondingPercent) || (b.volumeUsd1h - a.volumeUsd1h))
  .slice(0, 30);

const graduated = uniqueByAddress(migratedTokens)
  .sort((a, b) => (b.migratedEndTimestamp - a.migratedEndTimestamp) || (b.volumeUsd1h - a.volumeUsd1h))
  .slice(0, 30);

const payload = {
  schemaVersion: 1,
  source: "OKX Onchain OS memepump",
  chain: "Solana",
  chainIndex: "501",
  fetchedAt: new Date().toISOString(),
  counts: {
    new: newTokens.length,
    migrating: migratingTokens.length,
    migrated: migratedTokens.length,
    ungraduated: ungraduated.length,
    graduated: graduated.length
  },
  ungraduated,
  graduated
};

await mkdir("docs/data", { recursive: true });
await writeFile(OUT_FILE, `${JSON.stringify(payload, null, 2)}\n`, "utf8");

console.log(`Wrote ${OUT_FILE}`);
console.log(`Ungraded: ${ungraduated.length}, graduated: ${graduated.length}`);
