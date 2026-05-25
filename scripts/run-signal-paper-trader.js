import { execFileSync } from "node:child_process";
import { existsSync, readFileSync } from "node:fs";
import { mkdir, readFile, writeFile } from "node:fs/promises";

const OUT_FILE = "docs/data/signal-paper.json";
const CHAINS = (process.env.SIGNAL_CHAINS || process.env.SIGNAL_CHAIN || "solana,bsc")
  .split(",")
  .map((chain) => chain.trim())
  .filter(Boolean);
const STARTING_CAPITAL_USD = 3000;

function loadDotEnv(path = ".env") {
  if (!existsSync(path)) return;
  const lines = readFileSync(path, "utf8").split(/\r?\n/);
  for (const line of lines) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith("#")) continue;
    const match = trimmed.match(/^([A-Za-z_][A-Za-z0-9_]*)=(.*)$/);
    if (!match) continue;
    const [, key, rawValue] = match;
    if (process.env[key]) continue;
    process.env[key] = rawValue.replace(/^['"]|['"]$/g, "");
  }
}

loadDotEnv();

const CONFIG = {
  quoteAsset: "USDT paper capital",
  scanChains: CHAINS,
  signalLimit: 50,
  signalWalletTypeParam: "2,3",
  smartMoneyResearchLimit: 20,
  smartMoneyResearchSoldRatioPercent: 80,
  includedWalletTypes: ["KOL/Influencer", "Whale"],
  excludedWalletTypes: ["Smart Money"],
  startingCapitalUsd: STARTING_CAPITAL_USD,
  reserveUsd: 900,
  maxOpenPositions: 8,
  maxNewBuysPerRun: 3,
  minBuyUsd: 120,
  maxBuyUsd: 450,
  feePct: 0.3,
  buyScoreThreshold: 70,
  watchScoreThreshold: 55,
  minSignalAmountUsd: 500,
  minTriggerWalletCount: 2,
  maxSoldRatioPercent: 35,
  stopLossPct: -25,
  takeProfitPct: 55,
  staleHoursBeforeReview: 6
};

function toNumber(value, fallback = 0) {
  if (value === null || value === undefined || value === "") return fallback;
  const parsed = Number(String(value).replace(/,/g, ""));
  return Number.isFinite(parsed) ? parsed : fallback;
}

function round(value, digits = 2) {
  const factor = 10 ** digits;
  return Math.round((toNumber(value) + Number.EPSILON) * factor) / factor;
}

function firstDefined(...values) {
  return values.find((value) => value !== undefined && value !== null && value !== "");
}

function shortAddress(address) {
  if (!address) return "";
  return address.length > 12 ? `${address.slice(0, 6)}...${address.slice(-4)}` : address;
}

function parseWalletAddresses(value) {
  if (Array.isArray(value)) return value.map((item) => String(item).trim()).filter(Boolean);
  return String(value || "")
    .split(/[,\s]+/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function positionKey(chain, address) {
  return `${String(chain || "").toLowerCase()}:${String(address || "").toLowerCase()}`;
}

function arrayFromData(payload) {
  if (Array.isArray(payload?.data)) return payload.data;
  if (Array.isArray(payload?.data?.list)) return payload.data.list;
  if (Array.isArray(payload?.data?.items)) return payload.data.items;
  if (Array.isArray(payload?.data?.signals)) return payload.data.signals;
  if (Array.isArray(payload?.result)) return payload.result;
  return [];
}

function runCli(args) {
  const command = `onchainos ${args.join(" ")}`;
  try {
    const stdout = execFileSync("onchainos", args, {
      encoding: "utf8",
      maxBuffer: 30 * 1024 * 1024
    });
    let parsed = null;
    try {
      parsed = JSON.parse(stdout);
    } catch (error) {
      return {
        ok: false,
        command,
        stdout,
        error: `CLI returned non-JSON output: ${error.message}`,
        notifications: []
      };
    }
    return {
      ok: Boolean(parsed.ok),
      confirming: Boolean(parsed.confirming),
      command,
      stdout,
      parsed,
      notifications: Array.isArray(parsed.notifications) ? parsed.notifications : [],
      error: parsed.error || ""
    };
  } catch (error) {
    const stdout = error.stdout?.toString?.() || "";
    let parsed = null;
    try {
      parsed = stdout ? JSON.parse(stdout) : null;
    } catch {
      parsed = null;
    }
    return {
      ok: false,
      command,
      stdout,
      parsed,
      notifications: Array.isArray(parsed?.notifications) ? parsed.notifications : [],
      error: parsed?.error || error.message || "CLI command failed"
    };
  }
}

async function readJson(path, fallback) {
  try {
    return JSON.parse(await readFile(path, "utf8"));
  } catch (error) {
    if (error.code === "ENOENT") return fallback;
    throw error;
  }
}

function newState(now) {
  return {
    schemaVersion: 1,
    mode: "signal-paper-auto",
    source: "OKX Onchain OS signal list",
    startedAt: now,
    updatedAt: now,
    config: CONFIG,
    capital: {
      initialUsd: STARTING_CAPITAL_USD,
      cashUsd: STARTING_CAPITAL_USD,
      openValueUsd: 0,
      equityUsd: STARTING_CAPITAL_USD,
      realizedPnlUsd: 0,
      unrealizedPnlUsd: 0,
      totalPnlUsd: 0,
      totalPnlPct: 0
    },
    positions: [],
    trades: [],
    decisions: [],
    runs: [],
    mistakes: [],
    session: {
      id: now.replace(/[-:.TZ]/g, "").slice(0, 14),
      startedAt: now,
      lastAuthOkAt: "",
      lastAuthFailureAt: "",
      authState: "unknown",
      authRecoveries: 0,
      resetReason: "initial"
    },
    accountResets: [],
    walletBlacklist: {
      updatedAt: now,
      entries: []
    },
    smartMoneyWatchlist: {
      updatedAt: now,
      entries: []
    },
    strategyArchive: {
      updatedAt: now,
      best: [],
      rejected: [],
      lessons: []
    }
  };
}

function normalizeState(state, now) {
  const base = state?.schemaVersion === 1 ? state : newState(now);
  base.config = { ...CONFIG, ...(base.config || {}) };
  base.capital = { ...newState(now).capital, ...(base.capital || {}) };
  base.positions = Array.isArray(base.positions) ? base.positions : [];
  base.trades = Array.isArray(base.trades) ? base.trades : [];
  base.decisions = Array.isArray(base.decisions) ? base.decisions : [];
  base.runs = Array.isArray(base.runs) ? base.runs : [];
  base.mistakes = Array.isArray(base.mistakes) ? base.mistakes : [];
  base.session = base.session && typeof base.session === "object"
    ? {
        id: base.session.id || (base.startedAt || now).replace(/[-:.TZ]/g, "").slice(0, 14),
        startedAt: base.session.startedAt || base.startedAt || now,
        lastAuthOkAt: base.session.lastAuthOkAt || "",
        lastAuthFailureAt: base.session.lastAuthFailureAt || "",
        authState: base.session.authState || "unknown",
        authRecoveries: toNumber(base.session.authRecoveries),
        resetReason: base.session.resetReason || "legacy"
      }
    : newState(now).session;
  base.accountResets = Array.isArray(base.accountResets) ? base.accountResets : [];
  base.walletBlacklist = base.walletBlacklist && typeof base.walletBlacklist === "object"
    ? base.walletBlacklist
    : { updatedAt: now, entries: [] };
  base.walletBlacklist.entries = Array.isArray(base.walletBlacklist.entries) ? base.walletBlacklist.entries : [];
  base.smartMoneyWatchlist = base.smartMoneyWatchlist && typeof base.smartMoneyWatchlist === "object"
    ? base.smartMoneyWatchlist
    : { updatedAt: now, entries: [] };
  base.smartMoneyWatchlist.entries = Array.isArray(base.smartMoneyWatchlist.entries) ? base.smartMoneyWatchlist.entries : [];
  base.strategyArchive = base.strategyArchive && typeof base.strategyArchive === "object"
    ? base.strategyArchive
    : { updatedAt: now, best: [], rejected: [], lessons: [] };
  base.strategyArchive.best = Array.isArray(base.strategyArchive.best) ? base.strategyArchive.best : [];
  base.strategyArchive.rejected = Array.isArray(base.strategyArchive.rejected) ? base.strategyArchive.rejected : [];
  base.strategyArchive.lessons = Array.isArray(base.strategyArchive.lessons) ? base.strategyArchive.lessons : [];
  return base;
}

function notificationSummary(notifications) {
  return notifications.map((item) => ({
    code: item.code || "",
    tier: item.data?.tier || "",
    paymentOptions: Array.isArray(item.data?.payment) ? item.data.payment.length : 0
  }));
}

function classifyIssue(result) {
  if (!result) return "";
  const text = `${result.error || ""} ${result.stdout || ""}`;
  if (/Invalid Authority/i.test(text)) return "AUTH_INVALID";
  if (/OVER_QUOTA|quota/i.test(text)) return "MARKET_API_QUOTA_OR_PAYMENT";
  if (/region|50125|80001/i.test(text)) return "REGION_RESTRICTED";
  if (/non-JSON/i.test(text)) return "NON_JSON_OUTPUT";
  if (result.confirming) return "PAYMENT_CONFIRMATION_REQUIRED";
  return result.ok ? "" : "CLI_ERROR";
}

function isAuthIssueType(type) {
  return type === "AUTH_INVALID";
}

function latestRunHadAuthFailure(state) {
  const latest = (state.runs || [])[0];
  return Boolean((latest?.mistakes || []).some((mistake) => isAuthIssueType(mistake.type)));
}

function hasUnrecoveredAuthFailure(session) {
  const failedAt = session?.lastAuthFailureAt ? new Date(session.lastAuthFailureAt).getTime() : 0;
  const okAt = session?.lastAuthOkAt ? new Date(session.lastAuthOkAt).getTime() : 0;
  return failedAt > 0 && failedAt >= okAt;
}

function resetPaperAccountForRelogin(state, now, run, reason) {
  const previousSession = { ...(state.session || {}) };
  const previousCapital = { ...(state.capital || {}) };
  const resetRecord = {
    timestamp: now,
    runId: run.id,
    reason,
    previousSession,
    previousCapital,
    previousOpenPositions: (state.positions || []).filter((item) => item.status === "open").length,
    previousTrades: (state.trades || []).length,
    previousDecisions: (state.decisions || []).length
  };

  state.accountResets.unshift(resetRecord);
  state.accountResets = state.accountResets.slice(0, 50);
  state.capital = { ...newState(now).capital };
  state.positions = [];
  state.trades = [];
  state.decisions = [];
  state.session = {
    id: run.id,
    startedAt: now,
    lastAuthOkAt: now,
    lastAuthFailureAt: "",
    authState: "online",
    authRecoveries: toNumber(previousSession.authRecoveries) + 1,
    resetReason: reason
  };
  run.accountReset = resetRecord;
  run.notes.push("授权恢复或重新登录后，已按规则重置模拟本金为 3000U。历史轮次保留用于审计，不混入新会话本金。");
}

function blacklistKey(chain, walletAddress) {
  return `${String(chain || "").toLowerCase()}:${String(walletAddress || "").toLowerCase()}`;
}

function blacklistHits(state, signal) {
  const entries = state.walletBlacklist?.entries || [];
  if (!entries.length || !signal.triggerWalletAddresses?.length) return [];
  const blocked = new Map(entries.map((entry) => [blacklistKey(entry.chain, entry.walletAddress), entry]));
  return signal.triggerWalletAddresses
    .map((walletAddress) => blocked.get(blacklistKey(signal.chain, walletAddress)))
    .filter(Boolean);
}

function upsertWalletBlacklist(state, trade, now) {
  if (trade.action !== "SELL" || toNumber(trade.realizedPnlUsd) >= 0) return;
  const walletAddresses = parseWalletAddresses(trade.triggerWalletAddresses);
  if (!walletAddresses.length) return;
  const entries = state.walletBlacklist.entries;
  for (const walletAddress of walletAddresses) {
    const key = blacklistKey(trade.chain, walletAddress);
    let entry = entries.find((item) => blacklistKey(item.chain, item.walletAddress) === key);
    if (!entry) {
      entry = {
        walletAddress,
        shortAddress: shortAddress(walletAddress),
        chain: trade.chain,
        walletType: trade.walletType,
        status: "blacklisted",
        firstSeenAt: now,
        lastSeenAt: now,
        lossCount: 0,
        totalLossUsd: 0,
        tokens: [],
        reasons: []
      };
      entries.push(entry);
    }
    entry.lastSeenAt = now;
    entry.lossCount = toNumber(entry.lossCount) + 1;
    entry.totalLossUsd = round(toNumber(entry.totalLossUsd) + Math.min(0, toNumber(trade.realizedPnlUsd)), 2);
    if (!entry.tokens.some((item) => item.address === trade.address)) {
      entry.tokens.unshift({
        token: trade.token,
        symbol: trade.symbol,
        address: trade.address,
        shortAddress: trade.shortAddress,
        runId: trade.runId,
        realizedPnlUsd: trade.realizedPnlUsd
      });
      entry.tokens = entry.tokens.slice(0, 10);
    }
    if (trade.reason && !entry.reasons.includes(trade.reason)) {
      entry.reasons.unshift(trade.reason);
      entry.reasons = entry.reasons.slice(0, 10);
    }
  }
  state.walletBlacklist.updatedAt = now;
  state.walletBlacklist.entries = entries
    .sort((a, b) => Math.abs(toNumber(b.totalLossUsd)) - Math.abs(toNumber(a.totalLossUsd)) || toNumber(b.lossCount) - toNumber(a.lossCount))
    .slice(0, 500);
}

function upsertSmartMoneyWatchlist(state, signal, now, reason) {
  if (signal.walletType !== "Smart Money" || !signal.triggerWalletAddresses.length) return;
  const entries = state.smartMoneyWatchlist.entries;
  for (const walletAddress of signal.triggerWalletAddresses) {
    const key = blacklistKey(signal.chain, walletAddress);
    let entry = entries.find((item) => blacklistKey(item.chain, item.walletAddress) === key);
    if (!entry) {
      entry = {
        walletAddress,
        shortAddress: shortAddress(walletAddress),
        chain: signal.chain,
        walletType: signal.walletType,
        status: "watch_only",
        firstSeenAt: now,
        lastSeenAt: now,
        occurrences: 0,
        highSoldRatioCount: 0,
        tokens: [],
        reasons: []
      };
      entries.push(entry);
    }
    entry.lastSeenAt = now;
    entry.occurrences = toNumber(entry.occurrences) + 1;
    if (signal.soldRatioPercent >= CONFIG.smartMoneyResearchSoldRatioPercent) {
      entry.highSoldRatioCount = toNumber(entry.highSoldRatioCount) + 1;
    }
    if (!entry.tokens.some((item) => item.address === signal.address)) {
      entry.tokens.unshift({
        token: signal.token,
        symbol: signal.symbol,
        address: signal.address,
        shortAddress: signal.shortAddress,
        soldRatioPercent: round(signal.soldRatioPercent, 2),
        amountUsd: round(signal.amountUsd, 2)
      });
      entry.tokens = entry.tokens.slice(0, 10);
    }
    if (reason && !entry.reasons.includes(reason)) {
      entry.reasons.unshift(reason);
      entry.reasons = entry.reasons.slice(0, 10);
    }
  }
  state.smartMoneyWatchlist.updatedAt = now;
  state.smartMoneyWatchlist.entries = entries
    .sort((a, b) => toNumber(b.highSoldRatioCount) - toNumber(a.highSoldRatioCount) || toNumber(b.occurrences) - toNumber(a.occurrences))
    .slice(0, 500);
}

function normalizeSignal(item, index, requestTime, fallbackChain) {
  const token = item.token || item.baseToken || {};
  const address = String(firstDefined(
    item.tokenAddress,
    item.tokenContractAddress,
    item.contractAddress,
    item.address,
    item.mint,
    token.address,
    token.tokenAddress
  ) || "").toLowerCase();
  const amountUsd = toNumber(firstDefined(
    item.amountUsd,
    item.totalAmountUsd,
    item.buyAmountUsd,
    item.valueUsd,
    item.volumeUsd,
    item.amount_usd
  ));
  const walletCount = toNumber(firstDefined(
    item.triggerWalletCount,
    item.walletCount,
    item.addressCount,
    item.count,
    item.smartMoneyCount,
    item.kolCount,
    item.whaleCount
  ));
  const soldRatioPercent = toNumber(firstDefined(item.soldRatioPercent, item.soldRatio, item.sellRatioPercent), 0);
  const priceUsd = toNumber(firstDefined(
    item.priceUsd,
    item.price,
    item.signalPrice,
    item.priceAtSignal,
    token.price,
    token.priceUsd
  ));
  const walletTypeValue = String(firstDefined(item.walletType, item.wallet_type, item.type) || "");
  const walletType =
    walletTypeValue === "1" ? "Smart Money" :
    walletTypeValue === "2" ? "KOL/Influencer" :
    walletTypeValue === "3" ? "Whale" :
    walletTypeValue || "Unknown";

  return {
    index,
    requestTime,
    token: firstDefined(item.tokenName, item.name, token.name, "(unknown)") || "(unknown)",
    symbol: firstDefined(item.symbol, item.tokenSymbol, token.symbol, "") || "",
    address,
    shortAddress: shortAddress(address),
    chain: firstDefined(item.chain, item.chainName, fallbackChain) || fallbackChain,
    walletType,
    triggerWalletAddresses: parseWalletAddresses(firstDefined(
      item.triggerWalletAddress,
      item.triggerWalletAddresses,
      item.walletAddress,
      item.walletAddresses,
      item.addresses
    )),
    amountUsd,
    walletCount,
    soldRatioPercent,
    priceUsd,
    cursor: firstDefined(item.cursor, item.nextCursor, ""),
    raw: item
  };
}

function scoreSignal(signal, state) {
  const isExcludedWalletType = CONFIG.excludedWalletTypes.includes(signal.walletType);
  const blockedWallets = blacklistHits(state, signal);
  const amountScore = Math.min(30, Math.log10(signal.amountUsd + 1) * 7);
  const walletScore = Math.min(25, signal.walletCount * 7);
  const soldScore = Math.max(0, 25 - signal.soldRatioPercent * 0.55);
  const typeScore =
    signal.walletType === "Whale" ? 10 :
    signal.walletType === "KOL/Influencer" ? 6 :
    signal.walletType === "Smart Money" ? -20 : 3;
  const completenessPenalty = (!signal.address ? 20 : 0) + (!signal.priceUsd ? 10 : 0);
  const score = Math.max(0, Math.min(100, amountScore + walletScore + soldScore + typeScore - completenessPenalty));
  const blockers = [];
  if (!signal.address) blockers.push("missing token address");
  if (!signal.priceUsd) blockers.push("missing signal price");
  if (isExcludedWalletType) blockers.push(`excluded wallet type: ${signal.walletType}`);
  for (const entry of blockedWallets.slice(0, 3)) blockers.push(`blacklisted source wallet: ${entry.shortAddress || shortAddress(entry.walletAddress)}`);
  if (signal.amountUsd < CONFIG.minSignalAmountUsd) blockers.push(`amount < ${CONFIG.minSignalAmountUsd}U`);
  if (signal.walletCount < CONFIG.minTriggerWalletCount) blockers.push(`wallet count < ${CONFIG.minTriggerWalletCount}`);
  if (signal.soldRatioPercent > CONFIG.maxSoldRatioPercent) blockers.push(`sold ratio > ${CONFIG.maxSoldRatioPercent}%`);
  return {
    score: round(score, 1),
    blockers,
    reason: [
      `amount ${round(signal.amountUsd, 2)}U`,
      `wallets ${signal.walletCount}`,
      `sold ${round(signal.soldRatioPercent, 2)}%`,
      `type ${signal.walletType}`
    ].join("; ")
  };
}

function buySizeUsd(score, cashUsd) {
  const usable = Math.max(0, cashUsd - CONFIG.reserveUsd);
  if (usable < CONFIG.minBuyUsd) return 0;
  const scaled = CONFIG.minBuyUsd + ((score - CONFIG.buyScoreThreshold) / 30) * (CONFIG.maxBuyUsd - CONFIG.minBuyUsd);
  return round(Math.min(CONFIG.maxBuyUsd, Math.max(CONFIG.minBuyUsd, scaled), usable), 2);
}

function makeTrade(runId, timestamp, action, signal, values) {
  return {
    id: `${runId}-${action}-${signal.address || signal.index}-${values.sequence}`,
    runId,
    timestamp,
    action,
    token: signal.token,
    symbol: signal.symbol,
    address: signal.address,
    shortAddress: signal.shortAddress,
    chain: signal.chain,
    walletType: signal.walletType,
    triggerWalletAddresses: signal.triggerWalletAddresses || [],
    signalAmountUsd: round(signal.amountUsd, 2),
    triggerWalletCount: signal.walletCount,
    soldRatioPercent: round(signal.soldRatioPercent, 2),
    signalPriceUsd: signal.priceUsd,
    ...values
  };
}

function executeSell(state, run, runId, timestamp, position, signal, analysis, sequence, reason) {
  const grossUsd = toNumber(position.lastValueUsd, position.costBasisUsd);
  const feeUsd = grossUsd * (CONFIG.feePct / 100);
  const netUsd = Math.max(0, grossUsd - feeUsd);
  const pnlUsd = netUsd - toNumber(position.costBasisUsd);
  position.status = "closed";
  position.closedAt = timestamp;
  position.closeReason = reason;
  position.lastUpdatedAt = timestamp;
  position.realizedPnlUsd = round(pnlUsd, 6);
  position.lastValueUsd = 0;
  state.capital.cashUsd = round(toNumber(state.capital.cashUsd) + netUsd, 6);

  const trade = makeTrade(runId, timestamp, "SELL", signal, {
    sequence,
    grossUsd: round(grossUsd, 2),
    netUsd: round(netUsd, 2),
    feeUsd: round(feeUsd, 2),
    units: position.units,
    score: analysis.score,
    triggerWalletAddresses: position.entrySignal?.triggerWalletAddresses || signal.triggerWalletAddresses || [],
    realizedPnlUsd: round(pnlUsd, 2),
    reason
  });
  state.trades.unshift(trade);
  run.trades.push(trade);
  upsertWalletBlacklist(state, trade, timestamp);
  return trade;
}

function updateCapital(state) {
  let openValueUsd = 0;
  let unrealizedPnlUsd = 0;
  for (const position of state.positions.filter((item) => item.status === "open")) {
    const value = toNumber(position.lastValueUsd, position.costBasisUsd);
    openValueUsd += value;
    unrealizedPnlUsd += value - toNumber(position.costBasisUsd);
  }
  const realizedPnlUsd = state.positions.reduce((sum, item) => sum + toNumber(item.realizedPnlUsd), 0);
  const equityUsd = toNumber(state.capital.cashUsd) + openValueUsd;
  state.capital = {
    initialUsd: STARTING_CAPITAL_USD,
    cashUsd: round(state.capital.cashUsd, 2),
    openValueUsd: round(openValueUsd, 2),
    equityUsd: round(equityUsd, 2),
    realizedPnlUsd: round(realizedPnlUsd, 2),
    unrealizedPnlUsd: round(unrealizedPnlUsd, 2),
    totalPnlUsd: round(equityUsd - STARTING_CAPITAL_USD, 2),
    totalPnlPct: round(((equityUsd - STARTING_CAPITAL_USD) / STARTING_CAPITAL_USD) * 100, 2)
  };
}

function strategyKey(prefix, fields) {
  return `${prefix}:${fields.map((field) => String(field ?? "").toLowerCase()).join(":")}`;
}

function sampleToken(item) {
  return {
    token: item.token,
    symbol: item.symbol,
    address: item.address,
    shortAddress: item.shortAddress,
    chain: item.chain
  };
}

function upsertArchiveEntry(list, entry, now) {
  const existing = list.find((item) => item.key === entry.key);
  if (!existing) {
    list.unshift({
      ...entry,
      firstSeenAt: now,
      lastSeenAt: now,
      occurrences: 1,
      examples: entry.example ? [entry.example] : []
    });
    return;
  }

  existing.lastSeenAt = now;
  existing.occurrences = toNumber(existing.occurrences) + 1;
  existing.score = round(Math.max(toNumber(existing.score), toNumber(entry.score)), 1);
  existing.totalPnlUsd = round(toNumber(existing.totalPnlUsd) + toNumber(entry.totalPnlUsd), 2);
  existing.wins = toNumber(existing.wins) + toNumber(entry.wins);
  existing.losses = toNumber(existing.losses) + toNumber(entry.losses);
  existing.status = entry.status || existing.status;
  existing.rule = entry.rule || existing.rule;
  existing.reason = entry.reason || existing.reason;
  if (entry.example && !existing.examples.some((item) => item.address === entry.example.address && item.chain === entry.example.chain)) {
    existing.examples.unshift(entry.example);
    existing.examples = existing.examples.slice(0, 6);
  }
}

function archiveStrategyLearnings(state, run, now) {
  const archive = state.strategyArchive;
  archive.updatedAt = now;

  for (const decision of run.decisions) {
    const chain = decision.chain || "unknown";
    const walletType = decision.walletType || "Unknown";
    const soldBucket = decision.soldRatioPercent <= 15 ? "sold<=15" : decision.soldRatioPercent <= 35 ? "sold<=35" : "sold>35";
    const amountBucket = decision.amountUsd >= 1500 ? "amount>=1500" : decision.amountUsd >= 500 ? "amount>=500" : "amount<500";
    const walletBucket = decision.triggerWalletCount >= 8 ? "wallets>=8" : decision.triggerWalletCount >= 2 ? "wallets>=2" : "wallets<2";

    if (decision.action === "BUY") {
      upsertArchiveEntry(archive.best, {
        key: strategyKey("entry", [chain, walletType, amountBucket, walletBucket, soldBucket]),
        title: `${chain} ${walletType} 入场模型`,
        status: "候选最优",
        rule: `评分 >= ${CONFIG.buyScoreThreshold}，金额/钱包数达标，已卖出比例 <= ${CONFIG.maxSoldRatioPercent}%`,
        reason: decision.reason,
        score: decision.score,
        wins: 0,
        losses: 0,
        totalPnlUsd: 0,
        example: sampleToken(decision)
      }, now);
    }

    for (const blocker of decision.blockers || []) {
      upsertArchiveEntry(archive.rejected, {
        key: strategyKey("blocker", [chain, walletType, blocker]),
        title: `${chain} ${walletType} 不及格条件`,
        status: "归档拦截",
        rule: blocker,
        reason: decision.reason,
        score: decision.score,
        wins: 0,
        losses: 0,
        totalPnlUsd: 0,
        example: sampleToken(decision)
      }, now);
    }
  }

  for (const trade of run.trades) {
    if (trade.action !== "SELL") continue;
    const pnl = toNumber(trade.realizedPnlUsd);
    const target = pnl >= 0 ? archive.best : archive.rejected;
    upsertArchiveEntry(target, {
      key: strategyKey(pnl >= 0 ? "exit-win" : "exit-loss", [trade.chain, trade.walletType, trade.reason]),
      title: pnl >= 0 ? `${trade.chain} 止盈/退出有效样本` : `${trade.chain} 亏损/止损样本`,
      status: pnl >= 0 ? "已验证盈利" : "已归档亏损",
      rule: trade.reason,
      reason: trade.reason,
      score: trade.score,
      wins: pnl >= 0 ? 1 : 0,
      losses: pnl < 0 ? 1 : 0,
      totalPnlUsd: pnl,
      example: sampleToken(trade)
    }, now);

    if (pnl < 0) {
      upsertArchiveEntry(archive.lessons, {
        key: strategyKey("lesson", [trade.chain, trade.address, trade.reason]),
        title: "亏损复盘",
        status: "需避免重复",
        rule: "触发止损或亏损退出后自动归档",
        reason: `${trade.token} ${trade.symbol || ""}: ${trade.reason}`,
        score: trade.score,
        wins: 0,
        losses: 1,
        totalPnlUsd: pnl,
        example: sampleToken(trade)
      }, now);
    }
  }

  for (const mistake of run.mistakes || []) {
    upsertArchiveEntry(archive.lessons, {
      key: strategyKey("mistake", [mistake.type, mistake.chain || "global"]),
      title: "执行踩坑",
      status: "流程问题",
      rule: mistake.lesson || "失败轮次必须照实记录",
      reason: mistake.message,
      score: 0,
      wins: 0,
      losses: 0,
      totalPnlUsd: 0,
      example: { token: mistake.type, symbol: mistake.chain || "global", address: "", shortAddress: "", chain: mistake.chain || "global" }
    }, now);
  }

  archive.best = archive.best
    .sort((a, b) => (b.wins - b.losses) - (a.wins - a.losses) || b.occurrences - a.occurrences || b.score - a.score)
    .slice(0, 80);
  archive.rejected = archive.rejected
    .sort((a, b) => b.occurrences - a.occurrences || b.losses - a.losses || b.score - a.score)
    .slice(0, 120);
  archive.lessons = archive.lessons
    .sort((a, b) => b.occurrences - a.occurrences || b.losses - a.losses)
    .slice(0, 80);
}

const now = new Date().toISOString();
const runId = now.replace(/[-:.TZ]/g, "").slice(0, 14);
const state = normalizeState(await readJson(OUT_FILE, null), now);
state.updatedAt = now;

const run = {
  id: runId,
  startedAt: now,
  finishedAt: "",
  chains: CHAINS,
  status: "started",
  commands: [],
  rawSignalCount: 0,
  decisions: [],
  trades: [],
  mistakes: [],
  notes: [],
  chainResults: []
};

const chainsResult = runCli(["signal", "chains"]);
run.commands.push({
  command: chainsResult.command,
  ok: chainsResult.ok,
  confirming: chainsResult.confirming,
  error: chainsResult.error,
  notifications: notificationSummary(chainsResult.notifications)
});

if (!chainsResult.ok || chainsResult.confirming) {
  const issue = classifyIssue(chainsResult);
  run.status = "failed";
  if (isAuthIssueType(issue)) {
    state.session.lastAuthFailureAt = now;
    state.session.authState = "auth_failed";
  }
  run.mistakes.push({
    type: issue,
    message: chainsResult.error || "Unable to verify supported signal chains",
    lesson: "Do not trade when source availability or payment/auth state is uncertain."
  });
  if (issue === "MARKET_API_QUOTA_OR_PAYMENT") {
    run.notes.push("Market API may require OKX Agent Payments Protocol confirmation. No payment was confirmed and no fake data was used.");
  }
} else {
  if (latestRunHadAuthFailure(state) || hasUnrecoveredAuthFailure(state.session)) {
    resetPaperAccountForRelogin(state, now, run, "auth_recovered_after_login");
  } else {
    state.session.lastAuthOkAt = now;
    state.session.authState = "online";
  }

  const openByAddress = new Map(
    state.positions
      .filter((item) => item.status === "open")
      .map((item) => [positionKey(item.chain, item.address), item])
  );
  let sequence = 1;
  let buysThisRun = 0;

  for (const chain of CHAINS) {
    const chainResult = {
      chain,
      status: "started",
      rawSignalCount: 0,
      trades: 0,
      smartMoneyResearchCount: 0,
      mistakes: []
    };
    const smartMoneyResearch = runCli([
      "signal",
      "list",
      "--chain",
      chain,
      "--limit",
      String(CONFIG.smartMoneyResearchLimit),
      "--wallet-type",
      "1"
    ]);
    run.commands.push({
      command: smartMoneyResearch.command,
      ok: smartMoneyResearch.ok,
      confirming: smartMoneyResearch.confirming,
      error: smartMoneyResearch.error,
      notifications: notificationSummary(smartMoneyResearch.notifications),
      purpose: "smart-money-watch-only"
    });
    if (smartMoneyResearch.ok && !smartMoneyResearch.confirming) {
      const researchSignals = arrayFromData(smartMoneyResearch.parsed).map((item, index) => normalizeSignal(item, index + 1, "", chain));
      chainResult.smartMoneyResearchCount = researchSignals.length;
      for (const signal of researchSignals) {
        if (signal.soldRatioPercent >= CONFIG.smartMoneyResearchSoldRatioPercent) {
          upsertSmartMoneyWatchlist(state, signal, now, `watch only; sold ratio ${round(signal.soldRatioPercent, 2)}%`);
        }
      }
    } else {
      chainResult.mistakes.push({
        type: classifyIssue(smartMoneyResearch),
        message: smartMoneyResearch.error || `Unable to research smart money wallets for ${chain}`,
        lesson: "Smart Money research is watch-only and must never create trades.",
        chain
      });
    }

    const listArgs = ["signal", "list", "--chain", chain, "--limit", String(CONFIG.signalLimit)];
    if (CONFIG.signalWalletTypeParam) listArgs.push("--wallet-type", CONFIG.signalWalletTypeParam);
    const listResult = runCli(listArgs);
    run.commands.push({
      command: listResult.command,
      ok: listResult.ok,
      confirming: listResult.confirming,
      error: listResult.error,
      notifications: notificationSummary(listResult.notifications)
    });

    if (!listResult.ok || listResult.confirming) {
      const issue = classifyIssue(listResult);
      const mistake = {
        type: issue,
        message: listResult.error || `Unable to fetch signal list for ${chain}`,
        lesson: "A failed chain scan is recorded as failed; never backfill trades from memory or guesses.",
        chain
      };
      chainResult.status = "failed";
      chainResult.mistakes.push(mistake);
      run.mistakes.push(mistake);
      run.chainResults.push(chainResult);
      continue;
    }

    const requestTime = listResult.parsed?.requestTime || listResult.parsed?.data?.requestTime || "";
    const signals = arrayFromData(listResult.parsed).map((item, index) => normalizeSignal(item, index + 1, requestTime, chain));
    chainResult.rawSignalCount = signals.length;
    chainResult.status = "ok";
    run.rawSignalCount += signals.length;

    for (const signal of signals) {
      const analysis = scoreSignal(signal, state);
      const existing = openByAddress.get(positionKey(signal.chain, signal.address));
      const decision = {
        timestamp: now,
        runId,
        token: signal.token,
        symbol: signal.symbol,
        address: signal.address,
        shortAddress: signal.shortAddress,
        chain: signal.chain,
        walletType: signal.walletType,
        triggerWalletAddresses: signal.triggerWalletAddresses,
        amountUsd: round(signal.amountUsd, 2),
        triggerWalletCount: signal.walletCount,
        soldRatioPercent: round(signal.soldRatioPercent, 2),
        signalPriceUsd: signal.priceUsd,
        score: analysis.score,
        action: "WATCH",
        buyUsd: 0,
        reason: analysis.reason,
        blockers: analysis.blockers,
        raw: signal.raw
      };

      const canBuy =
        !existing &&
        buysThisRun < CONFIG.maxNewBuysPerRun &&
        openByAddress.size < CONFIG.maxOpenPositions &&
        analysis.score >= CONFIG.buyScoreThreshold &&
        analysis.blockers.length === 0;

      if (canBuy) {
        const grossUsd = buySizeUsd(analysis.score, state.capital.cashUsd);
        if (grossUsd >= CONFIG.minBuyUsd) {
          const feeUsd = grossUsd * (CONFIG.feePct / 100);
          const netUsd = grossUsd - feeUsd;
          const units = netUsd / signal.priceUsd;
          state.capital.cashUsd = round(state.capital.cashUsd - grossUsd, 6);
          const position = {
            id: `${signal.address}-${runId}`,
            status: "open",
            token: signal.token,
            symbol: signal.symbol,
            address: signal.address,
            shortAddress: signal.shortAddress,
            chain: signal.chain,
            openedAt: now,
            lastUpdatedAt: now,
            entryPriceUsd: signal.priceUsd,
            lastPriceUsd: signal.priceUsd,
            units,
            costBasisUsd: round(grossUsd, 6),
            lastValueUsd: round(netUsd, 6),
            realizedPnlUsd: 0,
            entrySignal: {
              amountUsd: round(signal.amountUsd, 2),
              triggerWalletCount: signal.walletCount,
              triggerWalletAddresses: signal.triggerWalletAddresses,
              soldRatioPercent: round(signal.soldRatioPercent, 2),
              walletType: signal.walletType,
              score: analysis.score
            }
          };
          state.positions.push(position);
            openByAddress.set(positionKey(signal.chain, signal.address), position);
            buysThisRun += 1;
          decision.action = "BUY";
          decision.buyUsd = round(grossUsd, 2);
          decision.feeUsd = round(feeUsd, 2);
          decision.reason = `Rule buy; ${analysis.reason}`;
          const trade = makeTrade(runId, now, "BUY", signal, {
            sequence,
            grossUsd: round(grossUsd, 2),
            netUsd: round(netUsd, 2),
            feeUsd: round(feeUsd, 2),
            units,
            score: analysis.score,
            reason: decision.reason
          });
          state.trades.unshift(trade);
          run.trades.push(trade);
          chainResult.trades += 1;
          sequence += 1;
        } else {
          decision.action = "SKIP";
          decision.blockers.push("insufficient cash above reserve");
        }
      } else if (existing) {
        existing.lastUpdatedAt = now;
        if (signal.priceUsd > 0) {
          existing.lastPriceUsd = signal.priceUsd;
          existing.lastValueUsd = round(existing.units * signal.priceUsd, 6);
        }
        const currentValueUsd = toNumber(existing.lastValueUsd, existing.costBasisUsd);
        const pnlPct = ((currentValueUsd - toNumber(existing.costBasisUsd)) / Math.max(1, toNumber(existing.costBasisUsd))) * 100;
        if (pnlPct <= CONFIG.stopLossPct) {
          const trade = executeSell(
            state,
            run,
            runId,
            now,
            existing,
            signal,
            analysis,
            sequence,
            `Stop loss ${round(pnlPct, 2)}%; ${analysis.reason}`
          );
          chainResult.trades += 1;
          sequence += 1;
          decision.action = "SELL";
          decision.sellUsd = trade.netUsd;
          decision.pnlUsd = trade.realizedPnlUsd;
          decision.reason = trade.reason;
        } else if (pnlPct >= CONFIG.takeProfitPct) {
          const trade = executeSell(
            state,
            run,
            runId,
            now,
            existing,
            signal,
            analysis,
            sequence,
            `Take profit ${round(pnlPct, 2)}%; ${analysis.reason}`
          );
          chainResult.trades += 1;
          sequence += 1;
          decision.action = "SELL";
          decision.sellUsd = trade.netUsd;
          decision.pnlUsd = trade.realizedPnlUsd;
          decision.reason = trade.reason;
        } else {
          decision.action = "HOLD";
          decision.pnlPct = round(pnlPct, 2);
          decision.reason = `Already holding; latest signal observed. ${analysis.reason}`;
        }
      } else if (analysis.score < CONFIG.watchScoreThreshold) {
        decision.action = "IGNORE";
      } else {
        decision.action = "WATCH";
      }

      run.decisions.push(decision);
    }

    if (!signals.length) {
      run.notes.push(`${chain}: signal endpoint returned zero rows. No trades were created.`);
    }
    run.chainResults.push(chainResult);
  }

  const okChains = run.chainResults.filter((item) => item.status === "ok").length;
  run.status = okChains > 0 ? (okChains === run.chainResults.length ? "ok" : "partial") : "failed";
}

const runDecisionSummaries = run.decisions.map((item) => ({
  timestamp: item.timestamp,
  runId: item.runId,
  token: item.token,
  symbol: item.symbol,
  address: item.address,
  shortAddress: item.shortAddress,
  chain: item.chain,
  walletType: item.walletType,
  triggerWalletAddresses: item.triggerWalletAddresses || [],
  action: item.action,
  score: item.score,
  amountUsd: item.amountUsd,
  triggerWalletCount: item.triggerWalletCount,
  soldRatioPercent: item.soldRatioPercent,
  signalPriceUsd: item.signalPriceUsd,
  buyUsd: item.buyUsd,
  feeUsd: item.feeUsd || 0,
  reason: item.reason,
  blockers: item.blockers || []
}));

state.decisions = [...runDecisionSummaries, ...state.decisions].slice(0, 500);
state.trades = state.trades.slice(0, 500);
state.positions = state.positions.slice(0, 100);
for (const mistake of run.mistakes) {
  state.mistakes.unshift({ ...mistake, runId, timestamp: now });
}
state.mistakes = state.mistakes.slice(0, 200);
updateCapital(state);
archiveStrategyLearnings(state, run, now);
run.finishedAt = new Date().toISOString();
run.capital = { ...state.capital };
state.runs.unshift(run);
state.runs = state.runs.slice(0, 200);

await mkdir("docs/data", { recursive: true });
await writeFile(OUT_FILE, `${JSON.stringify(state, null, 2)}\n`, "utf8");

console.log(`Wrote ${OUT_FILE}`);
console.log(`Run ${run.status}: signals=${run.rawSignalCount}, trades=${run.trades.length}, mistakes=${run.mistakes.length}`);
console.log(`Equity=${state.capital.equityUsd}U, cash=${state.capital.cashUsd}U, open=${state.capital.openValueUsd}U`);
