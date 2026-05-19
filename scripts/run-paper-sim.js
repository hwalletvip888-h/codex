import { mkdir, readFile, writeFile } from "node:fs/promises";

const MEME_FILE = "docs/data/meme.json";
const OUT_FILE = "docs/data/simulation.json";

const STARTING_CAPITAL_USD = 1000;
const CONFIG = {
  quoteAsset: "SOL 等值本金，按 U 计价",
  maxOpenPositions: 6,
  reserveUsd: 300,
  maxPositionUsd: 130,
  maxNewPositionsPerRun: 3,
  minOrderUsd: 25,
  feePct: 0.3,
  maxBuySlippagePct: 14,
  maxSellSlippagePct: 18,
  stalePositionHaircutPct: 18,
  buyScoreThreshold: 58,
  watchScoreThreshold: 48,
  stopLossPct: -28,
  takeProfitPct: 65
};

function toNumber(value) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

function clamp(value, min, max) {
  return Math.min(max, Math.max(min, value));
}

function round(value, digits = 2) {
  const factor = 10 ** digits;
  return Math.round((toNumber(value) + Number.EPSILON) * factor) / factor;
}

function safeRatio(numerator, denominator, fallback = 0) {
  const den = toNumber(denominator);
  if (den <= 0) {
    return fallback;
  }
  return toNumber(numerator) / den;
}

async function readJson(path, fallback = null) {
  try {
    return JSON.parse(await readFile(path, "utf8"));
  } catch (error) {
    if (error.code === "ENOENT") {
      return fallback;
    }
    throw error;
  }
}

function buySellStats(token) {
  const buys = toNumber(token.buyTxCount1h);
  const sells = toNumber(token.sellTxCount1h);
  const total = buys + sells;
  const buyRatio = total > 0 ? buys / total : 0.5;
  return {
    buys,
    sells,
    total,
    buyRatio,
    sellRatio: 1 - buyRatio
  };
}

function effectiveDepthUsd(token) {
  const volumeDepth = toNumber(token.volumeUsd1h) * 0.08;
  const marketDepth = toNumber(token.marketCapUsd) * 0.006;
  const holderDepth = toNumber(token.holders) * 2;
  return Math.max(120, Math.min(Math.max(volumeDepth, 80), Math.max(marketDepth, 80)) + holderDepth);
}

function estimateSlippagePct(token, notionalUsd, side) {
  const amount = Math.max(0, toNumber(notionalUsd));
  if (amount <= 0) {
    return 0;
  }

  const top10 = toNumber(token.top10HoldingsPercent);
  const snipers = toNumber(token.snipersPercent);
  const bundlers = toNumber(token.bundlersPercent);
  const holders = toNumber(token.holders);
  const depth = effectiveDepthUsd(token);
  const pressure = Math.pow(amount / depth, 0.85);
  const sideImpact = side === "sell" ? 9.5 : 8;
  const riskAdder =
    (top10 >= 35 ? 1.4 : 0) +
    (snipers >= 25 ? 1.2 : 0) +
    (bundlers >= 12 ? 0.8 : 0) +
    (holders > 0 && holders < 50 ? 0.9 : 0);

  return round(clamp(0.7 + pressure * sideImpact + riskAdder, 0.5, 35), 2);
}

function scoreToken(token) {
  const bonding = toNumber(token.bondingPercent);
  const volume = toNumber(token.volumeUsd1h);
  const marketCap = toNumber(token.marketCapUsd);
  const holders = toNumber(token.holders);
  const top10 = toNumber(token.top10HoldingsPercent);
  const dev = toNumber(token.devHoldingsPercent);
  const bundlers = toNumber(token.bundlersPercent);
  const snipers = toNumber(token.snipersPercent);
  const phishing = toNumber(token.suspectedPhishingWalletPercent);
  const stats = buySellStats(token);

  const bondingScore = clamp(((bonding - 78) / 22) * 24, 0, 24) - (bonding >= 99.7 ? 3 : 0);
  const volumeScore = clamp(((Math.log10(volume + 1) - 3) / 2.2) * 20, 0, 20);
  const buyPressureScore = clamp(((stats.buyRatio - 0.45) / 0.4) * 18, 0, 18);
  const holderScore = clamp(((Math.log10(holders + 1) - 1.25) / 1.45) * 14, 0, 14);
  const activityScore = clamp((stats.total / 160) * 9, 0, 9);
  const stageScore = token.stage === "MIGRATING" ? 7 : token.stage === "NEW" ? 3 : 0;

  const riskPenalty =
    Math.max(0, top10 - 25) * 0.42 +
    Math.max(0, snipers - 18) * 0.35 +
    Math.max(0, bundlers - 8) * 0.4 +
    Math.max(0, dev - 8) * 0.75 +
    Math.max(0, phishing - 2) * 1.2 +
    (holders > 0 && holders < 35 ? 4 : 0);

  const hardBlock =
    marketCap <= 0 ||
    holders < 10 ||
    top10 >= 55 ||
    snipers >= 55 ||
    dev >= 20 ||
    phishing >= 10;

  const score = hardBlock
    ? clamp(bondingScore + volumeScore + buyPressureScore - riskPenalty, 0, 42)
    : clamp(bondingScore + volumeScore + buyPressureScore + holderScore + activityScore + stageScore - riskPenalty, 0, 100);

  const reasons = [];
  reasons.push(`进度 ${round(bonding, 1)}%`);
  reasons.push(`买盘 ${round(stats.buyRatio * 100, 1)}%`);
  reasons.push(`1小时量 ${round(volume, 0)}U`);
  reasons.push(`持币 ${holders}`);
  if (top10 >= 55) reasons.push("Top10过度集中");
  if (snipers >= 30) reasons.push("狙击占比偏高");
  if (bundlers >= 12) reasons.push("捆绑占比偏高");
  if (dev >= 12) reasons.push("开发者持仓偏高");
  if (phishing >= 5) reasons.push("疑似钓鱼钱包偏高");

  return {
    score: round(score, 1),
    hardBlock,
    buyRatio: stats.buyRatio,
    sellRatio: stats.sellRatio,
    reason: reasons.join("；")
  };
}

function candidateBuyUsd(token, score, cashUsd, openCount) {
  if (openCount >= CONFIG.maxOpenPositions) {
    return 0;
  }
  const usableCash = Math.max(0, cashUsd - CONFIG.reserveUsd);
  if (usableCash < CONFIG.minOrderUsd) {
    return 0;
  }

  const scoreScale = clamp((score - CONFIG.buyScoreThreshold) / 32, 0, 1);
  const desired = 35 + scoreScale * 95;
  const volumeCap = Math.max(CONFIG.minOrderUsd, toNumber(token.volumeUsd1h) * 0.025);
  const sized = Math.min(desired, volumeCap, CONFIG.maxPositionUsd, usableCash);
  return sized >= CONFIG.minOrderUsd ? round(sized, 2) : 0;
}

function newState(now) {
  return {
    schemaVersion: 1,
    mode: "paper-auto",
    source: "OKX Onchain OS memepump",
    chain: "Solana",
    config: CONFIG,
    startedAt: now,
    updatedAt: now,
    sourceMemeFetchedAt: "",
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
    snapshots: []
  };
}

function normalizeState(state, now) {
  const base = state && state.schemaVersion === 1 ? state : newState(now);
  base.config = { ...CONFIG, ...(base.config ?? {}) };
  base.capital = {
    ...newState(now).capital,
    ...(base.capital ?? {})
  };
  base.positions = Array.isArray(base.positions) ? base.positions : [];
  base.trades = Array.isArray(base.trades) ? base.trades : [];
  base.decisions = [];
  base.snapshots = Array.isArray(base.snapshots) ? base.snapshots : [];
  return base;
}

function makeTrade(now, runId, action, token, values) {
  return {
    id: `${runId}-${action}-${token.address}-${values.sequence}`,
    timestamp: now,
    action,
    token: token.name,
    symbol: token.symbol,
    address: token.address,
    shortAddress: token.shortAddress,
    stage: token.stage,
    stageLabel: token.stageLabel,
    protocol: token.protocol,
    ...values
  };
}

function tokenSnapshot(token, analysis, decision, values = {}) {
  const buySlip = estimateSlippagePct(token, values.buyUsd ?? 0, "buy");
  const sellSlip = estimateSlippagePct(token, values.sellUsd ?? values.estimatedSellUsd ?? 0, "sell");
  return {
    token: token.name,
    symbol: token.symbol,
    address: token.address,
    shortAddress: token.shortAddress,
    stage: token.stage,
    stageLabel: token.stageLabel,
    protocol: token.protocol,
    bondingPercent: round(token.bondingPercent, 2),
    marketCapUsd: round(token.marketCapUsd, 2),
    volumeUsd1h: round(token.volumeUsd1h, 2),
    buyTxCount1h: toNumber(token.buyTxCount1h),
    sellTxCount1h: toNumber(token.sellTxCount1h),
    buyRatioPct: round(analysis.buyRatio * 100, 2),
    holders: toNumber(token.holders),
    top10HoldingsPercent: round(token.top10HoldingsPercent, 2),
    score: analysis.score,
    decision,
    buyUsd: round(values.buyUsd ?? 0, 2),
    sellUsd: round(values.sellUsd ?? 0, 2),
    estimatedSellUsd: round(values.estimatedSellUsd ?? 0, 2),
    buySlippagePct: buySlip,
    sellSlippagePct: sellSlip,
    feeUsd: round(values.feeUsd ?? 0, 2),
    pnlUsd: round(values.pnlUsd ?? 0, 2),
    reason: values.reason ?? analysis.reason
  };
}

function executeBuy(state, token, analysis, buyUsd, now, runId, sequence) {
  const slippagePct = estimateSlippagePct(token, buyUsd, "buy");
  const slippageUsd = buyUsd * (slippagePct / 100);
  const feeUsd = buyUsd * (CONFIG.feePct / 100);
  const netUsd = Math.max(0, buyUsd - slippageUsd - feeUsd);
  const marketCap = Math.max(1, toNumber(token.marketCapUsd));
  const units = netUsd / marketCap;

  state.capital.cashUsd = round(state.capital.cashUsd - buyUsd, 6);
  state.positions.push({
    id: token.address,
    token: token.name,
    symbol: token.symbol,
    address: token.address,
    shortAddress: token.shortAddress,
    protocol: token.protocol,
    openedAt: now,
    lastUpdatedAt: now,
    stage: token.stage,
    stageLabel: token.stageLabel,
    entryMarketCapUsd: round(token.marketCapUsd, 2),
    lastMarketCapUsd: round(token.marketCapUsd, 2),
    units,
    costBasisUsd: round(buyUsd, 6),
    realizedPnlUsd: 0,
    status: "open",
    graduationSellDone: false,
    profitSellDone: false
  });

  const trade = makeTrade(now, runId, "BUY", token, {
    sequence,
    grossUsd: round(buyUsd, 2),
    netUsd: round(netUsd, 2),
    slippagePct,
    slippageUsd: round(slippageUsd, 2),
    feeUsd: round(feeUsd, 2),
    marketCapUsd: round(token.marketCapUsd, 2),
    score: analysis.score,
    reason: analysis.reason
  });
  state.trades.unshift(trade);

  return {
    trade,
    decision: tokenSnapshot(token, analysis, "模拟买入", {
      buyUsd,
      feeUsd,
      reason: `按规则开仓；${analysis.reason}`
    })
  };
}

function executeSell(state, position, token, analysis, fraction, now, runId, sequence, reason) {
  const sellFraction = clamp(fraction, 0, 1);
  const sellUnits = position.units * sellFraction;
  const grossUsd = sellUnits * Math.max(1, toNumber(token.marketCapUsd));
  const slippagePct = estimateSlippagePct(token, grossUsd, "sell");
  const slippageUsd = grossUsd * (slippagePct / 100);
  const feeUsd = grossUsd * (CONFIG.feePct / 100);
  const netUsd = Math.max(0, grossUsd - slippageUsd - feeUsd);
  const costOut = position.costBasisUsd * sellFraction;
  const pnlUsd = netUsd - costOut;

  position.units = Math.max(0, position.units - sellUnits);
  position.costBasisUsd = round(Math.max(0, position.costBasisUsd - costOut), 6);
  position.realizedPnlUsd = round(toNumber(position.realizedPnlUsd) + pnlUsd, 6);
  position.lastUpdatedAt = now;
  position.stage = token.stage;
  position.stageLabel = token.stageLabel;
  position.lastMarketCapUsd = round(token.marketCapUsd, 2);
  state.capital.cashUsd = round(state.capital.cashUsd + netUsd, 6);

  if (position.units <= 1e-12 || position.costBasisUsd <= 1) {
    position.status = "closed";
    position.closedAt = now;
    position.units = 0;
    position.costBasisUsd = 0;
  }

  const trade = makeTrade(now, runId, "SELL", token, {
    sequence,
    grossUsd: round(grossUsd, 2),
    netUsd: round(netUsd, 2),
    slippagePct,
    slippageUsd: round(slippageUsd, 2),
    feeUsd: round(feeUsd, 2),
    marketCapUsd: round(token.marketCapUsd, 2),
    score: analysis.score,
    realizedPnlUsd: round(pnlUsd, 2),
    reason
  });
  state.trades.unshift(trade);

  return {
    trade,
    decision: tokenSnapshot(token, analysis, "模拟卖出", {
      sellUsd: netUsd,
      feeUsd,
      pnlUsd,
      reason
    })
  };
}

function shouldSell(position, token, analysis, liquidationValueUsd) {
  const cost = Math.max(1, toNumber(position.costBasisUsd));
  const pnlPct = ((liquidationValueUsd - cost) / cost) * 100;
  const stats = buySellStats(token);

  if (analysis.hardBlock) {
    return { fraction: 1, reason: "风险硬拦截触发，纸面全卖" };
  }
  if (pnlPct <= CONFIG.stopLossPct) {
    return { fraction: 1, reason: `触发 ${CONFIG.stopLossPct}% 纸面止损` };
  }
  if (token.stage === "MIGRATED" && !position.graduationSellDone) {
    position.graduationSellDone = true;
    return { fraction: stats.buyRatio >= 0.52 ? 0.5 : 1, reason: "观察到毕业，按规则先卖出一部分或全部" };
  }
  if (pnlPct >= CONFIG.takeProfitPct && !position.profitSellDone) {
    position.profitSellDone = true;
    return { fraction: 0.5, reason: `达到 ${CONFIG.takeProfitPct}% 纸面止盈线` };
  }
  if (stats.buyRatio < 0.38 && stats.sells >= 8) {
    return { fraction: 0.5, reason: "1小时卖盘明显占优，纸面减仓" };
  }
  if (analysis.score < 40) {
    return { fraction: 0.5, reason: "综合评分跌破持仓线，纸面减仓" };
  }
  return null;
}

function summarizeOpenPosition(position, token, analysis) {
  const grossValue = position.units * Math.max(1, toNumber(token.marketCapUsd));
  const sellSlip = estimateSlippagePct(token, grossValue, "sell");
  const liquidation = Math.max(0, grossValue - grossValue * (sellSlip / 100) - grossValue * (CONFIG.feePct / 100));
  position.lastLiquidationUsd = round(liquidation, 6);
  position.lastUnrealizedPnlUsd = round(liquidation - toNumber(position.costBasisUsd), 6);
  return {
    grossValue,
    liquidation,
    pnlUsd: liquidation - toNumber(position.costBasisUsd),
    decision: tokenSnapshot(token, analysis, "继续持仓", {
      estimatedSellUsd: liquidation,
      pnlUsd: liquidation - toNumber(position.costBasisUsd),
      reason: `持仓跟踪；${analysis.reason}`
    })
  };
}

function summarizeStaleOpenPosition(position) {
  const grossValue = position.units * Math.max(1, toNumber(position.lastMarketCapUsd || position.entryMarketCapUsd));
  const haircutUsd = grossValue * (CONFIG.stalePositionHaircutPct / 100);
  const feeUsd = grossValue * (CONFIG.feePct / 100);
  const liquidation = Math.max(0, grossValue - haircutUsd - feeUsd);
  const pnlUsd = liquidation - toNumber(position.costBasisUsd);
  position.lastLiquidationUsd = round(liquidation, 6);
  position.lastUnrealizedPnlUsd = round(pnlUsd, 6);

  return {
    liquidation,
    pnlUsd,
    decision: {
      token: position.token,
      symbol: position.symbol,
      address: position.address,
      shortAddress: position.shortAddress,
      stage: position.stage,
      stageLabel: position.stageLabel,
      protocol: position.protocol,
      bondingPercent: 0,
      marketCapUsd: round(position.lastMarketCapUsd || position.entryMarketCapUsd, 2),
      volumeUsd1h: 0,
      buyTxCount1h: 0,
      sellTxCount1h: 0,
      buyRatioPct: 0,
      holders: 0,
      top10HoldingsPercent: 0,
      score: 0,
      decision: "数据暂缺",
      buyUsd: 0,
      sellUsd: 0,
      estimatedSellUsd: round(liquidation, 2),
      buySlippagePct: 0,
      sellSlippagePct: CONFIG.stalePositionHaircutPct,
      feeUsd: round(feeUsd, 2),
      pnlUsd: round(pnlUsd, 2),
      reason: "当前不在 OKX memepump 返回列表内，按最后已知市值保守折价估值，等待下一轮数据"
    }
  };
}

const now = new Date().toISOString();
const runId = now.replace(/[-:.TZ]/g, "").slice(0, 14);
const meme = await readJson(MEME_FILE);
const previous = await readJson(OUT_FILE, null);
const state = normalizeState(previous, now);
state.updatedAt = now;
state.sourceMemeFetchedAt = meme.fetchedAt;

const allTokens = [...(meme.ungraduated ?? []), ...(meme.graduated ?? [])];
const byAddress = new Map(allTokens.map((token) => [token.address, token]));
const currentDecisions = [];
let sequence = 1;

for (const position of state.positions.filter((item) => item.status === "open")) {
  const token = byAddress.get(position.address);
  if (!token) {
    currentDecisions.push(summarizeStaleOpenPosition(position).decision);
    continue;
  }

  const analysis = scoreToken(token);
  position.lastUpdatedAt = now;
  position.stage = token.stage;
  position.stageLabel = token.stageLabel;
  position.lastMarketCapUsd = round(token.marketCapUsd, 2);
  const summary = summarizeOpenPosition(position, token, analysis);
  const sell = shouldSell(position, token, analysis, summary.liquidation);

  if (sell) {
    const result = executeSell(state, position, token, analysis, sell.fraction, now, runId, sequence, sell.reason);
    currentDecisions.push(result.decision);
    sequence += 1;
  } else {
    currentDecisions.push(summary.decision);
  }
}

const openAddresses = new Set(state.positions.filter((item) => item.status === "open").map((item) => item.address));
const latestSnapshot = state.snapshots[0];
const entryBatchAlreadyUsed =
  state.lastEntrySourceMemeFetchedAt === meme.fetchedAt ||
  (latestSnapshot?.sourceMemeFetchedAt === meme.fetchedAt && toNumber(latestSnapshot.tradesThisRun) > 0);
let buysThisRun = 0;
const candidates = (meme.ungraduated ?? [])
  .map((token) => ({ token, analysis: scoreToken(token) }))
  .sort((a, b) => b.analysis.score - a.analysis.score);

for (const { token, analysis } of candidates) {
  if (openAddresses.has(token.address)) {
    continue;
  }

  const buyUsd = candidateBuyUsd(token, analysis.score, state.capital.cashUsd, openAddresses.size);
  const buySlippagePct = estimateSlippagePct(token, buyUsd, "buy");
  const nearGraduation = toNumber(token.bondingPercent) >= 82;
  const buyPressureOk = analysis.buyRatio >= 0.54;
  const volumeOk = toNumber(token.volumeUsd1h) >= 750;
  const holdersOk = toNumber(token.holders) >= 25;
  const canBuy =
    !entryBatchAlreadyUsed &&
    buysThisRun < CONFIG.maxNewPositionsPerRun &&
    buyUsd > 0 &&
    !analysis.hardBlock &&
    nearGraduation &&
    buyPressureOk &&
    volumeOk &&
    holdersOk &&
    analysis.score >= CONFIG.buyScoreThreshold &&
    buySlippagePct <= CONFIG.maxBuySlippagePct;

  if (canBuy) {
    const result = executeBuy(state, token, analysis, buyUsd, now, runId, sequence);
    currentDecisions.push(result.decision);
    openAddresses.add(token.address);
    buysThisRun += 1;
    state.lastEntrySourceMemeFetchedAt = meme.fetchedAt;
    sequence += 1;
  } else if (currentDecisions.length < 28 && analysis.score >= CONFIG.watchScoreThreshold) {
    const reason = analysis.hardBlock
      ? `纸面跳过；${analysis.reason}`
      : `继续观察；${analysis.reason}`;
    currentDecisions.push(
      tokenSnapshot(token, analysis, analysis.hardBlock ? "跳过" : "观察", {
        reason
      })
    );
  }
}

let openValueUsd = 0;
let unrealizedPnlUsd = 0;
for (const position of state.positions.filter((item) => item.status === "open")) {
  const token = byAddress.get(position.address);
  if (!token) {
    const stale = summarizeStaleOpenPosition(position);
    openValueUsd += stale.liquidation;
    unrealizedPnlUsd += stale.pnlUsd;
    continue;
  }
  const analysis = scoreToken(token);
  const summary = summarizeOpenPosition(position, token, analysis);
  openValueUsd += summary.liquidation;
  unrealizedPnlUsd += summary.pnlUsd;
}

const realizedPnlUsd = state.positions.reduce((sum, position) => sum + toNumber(position.realizedPnlUsd), 0);
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

state.positions = state.positions
  .filter((position) => position.status === "open" || toNumber(position.realizedPnlUsd) !== 0)
  .slice(0, 80);
state.trades = state.trades.slice(0, 300);
state.decisions = currentDecisions
  .sort((a, b) => {
    const priority = { "模拟卖出": 5, "模拟买入": 4, "继续持仓": 3, "观察": 2, "跳过": 1, "数据暂缺": 0 };
    return (priority[b.decision] ?? 0) - (priority[a.decision] ?? 0) || b.score - a.score;
  })
  .slice(0, 30);
state.snapshots.unshift({
  timestamp: now,
  sourceMemeFetchedAt: meme.fetchedAt,
  cashUsd: state.capital.cashUsd,
  openValueUsd: state.capital.openValueUsd,
  equityUsd: state.capital.equityUsd,
  totalPnlUsd: state.capital.totalPnlUsd,
  openPositions: state.positions.filter((item) => item.status === "open").length,
  tradesThisRun: sequence - 1,
  buysThisRun
});
state.snapshots = state.snapshots.slice(0, 500);

await mkdir("docs/data", { recursive: true });
await writeFile(OUT_FILE, `${JSON.stringify(state, null, 2)}\n`, "utf8");

console.log(`Wrote ${OUT_FILE}`);
console.log(`Equity: ${state.capital.equityUsd}U, cash: ${state.capital.cashUsd}U, open: ${state.capital.openValueUsd}U`);
console.log(`Decisions: ${state.decisions.length}, trades this run: ${sequence - 1}`);
