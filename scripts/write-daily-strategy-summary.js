import { mkdir, readFile, writeFile } from "node:fs/promises";

const LEDGER_FILE = "docs/data/signal-paper.json";
const SUMMARY_FILE = "docs/data/daily-strategy-summary.json";
const OPERATION_LOG_FILE = "docs/data/operation-log.json";
const REPORT_DIR = "docs/reports";
const HK_TIME_ZONE = "Asia/Hong_Kong";

const hkDay = new Intl.DateTimeFormat("en-CA", {
  timeZone: HK_TIME_ZONE,
  year: "numeric",
  month: "2-digit",
  day: "2-digit"
});

function n(value) {
  return Number.isFinite(Number(value)) ? Number(value) : 0;
}

function round(value, digits = 2) {
  const factor = 10 ** digits;
  return Math.round((n(value) + Number.EPSILON) * factor) / factor;
}

function dayKey(value) {
  const date = new Date(value || Date.now());
  return Number.isNaN(date.getTime()) ? hkDay.format(new Date()) : hkDay.format(date);
}

function countBy(items, keyFn) {
  const map = new Map();
  for (const item of items) {
    const key = keyFn(item);
    map.set(key, (map.get(key) || 0) + 1);
  }
  return Object.fromEntries([...map.entries()].sort((a, b) => b[1] - a[1]));
}

function topEntries(record, limit = 8) {
  return Object.entries(record || {})
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([name, count]) => ({ name, count }));
}

async function readJson(path) {
  return JSON.parse(await readFile(path, "utf8"));
}

function runToOperation(run) {
  return {
    runId: run.id || "",
    startedAt: run.startedAt || "",
    finishedAt: run.finishedAt || "",
    status: run.status || "unknown",
    chains: run.chains || [],
    rawSignalCount: n(run.rawSignalCount),
    decisions: (run.decisions || []).length,
    trades: (run.trades || []).length,
    mistakes: (run.mistakes || []).map((item) => ({
      type: item.type || "",
      chain: item.chain || "",
      message: item.message || "",
      lesson: item.lesson || ""
    })),
    notes: run.notes || [],
    chainResults: (run.chainResults || []).map((item) => ({
      chain: item.chain,
      status: item.status,
      rawSignalCount: n(item.rawSignalCount),
      trades: n(item.trades),
      mistakes: item.mistakes || []
    })),
    accountReset: run.accountReset || null,
    capital: run.capital || null
  };
}

function summarizeDay(day, ledger) {
  const runs = (ledger.runs || [])
    .filter((run) => dayKey(run.startedAt) === day)
    .sort((a, b) => new Date(a.startedAt) - new Date(b.startedAt));
  const runIds = new Set(runs.map((run) => run.id));
  const decisions = (ledger.decisions || []).filter((item) => runIds.has(item.runId));
  const trades = (ledger.trades || []).filter((item) => runIds.has(item.runId));
  const mistakes = (ledger.mistakes || []).filter((item) => runIds.has(item.runId));
  const blockers = {};
  for (const decision of decisions) {
    for (const blocker of decision.blockers || []) blockers[blocker] = (blockers[blocker] || 0) + 1;
  }
  const firstCapital = runs[0]?.capital || ledger.capital || {};
  const lastCapital = runs.at(-1)?.capital || ledger.capital || {};
  const buyTrades = trades.filter((item) => item.action === "BUY");
  const sellTrades = trades.filter((item) => item.action === "SELL");
  const realizedPnl = sellTrades.reduce((sum, item) => sum + n(item.realizedPnlUsd), 0);

  return {
    date: day,
    timeZone: HK_TIME_ZONE,
    generatedAt: new Date().toISOString(),
    runCount: runs.length,
    statuses: countBy(runs, (run) => run.status || "unknown"),
    rawSignalCount: runs.reduce((sum, run) => sum + n(run.rawSignalCount), 0),
    decisionCount: decisions.length,
    actions: countBy(decisions, (item) => item.action || "UNKNOWN"),
    tradeCount: trades.length,
    buys: buyTrades.length,
    sells: sellTrades.length,
    buyUsd: round(buyTrades.reduce((sum, item) => sum + n(item.grossUsd), 0)),
    realizedPnlUsd: round(realizedPnl),
    equityStartUsd: round(firstCapital.equityUsd),
    equityEndUsd: round(lastCapital.equityUsd),
    equityChangeUsd: round(n(lastCapital.equityUsd) - n(firstCapital.equityUsd)),
    topBlockers: topEntries(blockers),
    mistakeCount: mistakes.length,
    mistakeTypes: countBy(mistakes, (item) => item.type || "UNKNOWN"),
    accountResets: (ledger.accountResets || []).filter((item) => dayKey(item.timestamp) === day).length,
    walletBlacklistCount: ledger.walletBlacklist?.entries?.length || 0,
    latestBlacklistedWallets: (ledger.walletBlacklist?.entries || []).slice(0, 5),
    smartMoneyWatchlistCount: ledger.smartMoneyWatchlist?.entries?.length || 0,
    latestSmartMoneyWatchlist: (ledger.smartMoneyWatchlist?.entries || []).slice(0, 5),
    bestStrategies: (ledger.strategyArchive?.best || []).slice(0, 5),
    rejectedStrategies: (ledger.strategyArchive?.rejected || []).slice(0, 5),
    lessons: (ledger.strategyArchive?.lessons || []).slice(0, 5),
    runs: runs.map((run) => runToOperation(run))
  };
}

function markdown(summary) {
  const lines = [
    `# ${summary.date} 策略模拟日报`,
    "",
    `生成时间：${summary.generatedAt}`,
    `时区：${summary.timeZone}`,
    "",
    "## 当日结果",
    "",
    `- 扫描轮次：${summary.runCount}`,
    `- 原始信号：${summary.rawSignalCount}`,
    `- 决策记录：${summary.decisionCount}`,
    `- 模拟成交：${summary.tradeCount} 笔，买入 ${summary.buys} 笔，卖出 ${summary.sells} 笔`,
    `- 买入金额：${summary.buyUsd}U`,
    `- 已实现盈亏：${summary.realizedPnlUsd}U`,
    `- 权益变化：${summary.equityStartUsd}U -> ${summary.equityEndUsd}U（${summary.equityChangeUsd}U）`,
    `- 账户重置：${summary.accountResets} 次`,
    `- 钱包黑名单：${summary.walletBlacklistCount} 个地址`,
    `- 聪明钱只读观察：${summary.smartMoneyWatchlistCount} 个地址`,
    "",
    "## 操作状态",
    "",
    ...Object.entries(summary.statuses).map(([status, count]) => `- ${status}: ${count} 轮`),
    "",
    "## 主要阻断条件",
    "",
    ...(summary.topBlockers.length ? summary.topBlockers.map((item) => `- ${item.name}: ${item.count} 次`) : ["- 暂无阻断记录"]),
    "",
    "## 今日复盘",
    "",
    summary.tradeCount
      ? "- 今日有模拟成交，后续按止盈/止损和信号延续情况继续验证策略质量。"
      : "- 今日没有满足买入条件的成交，优先观察阻断条件是否过严或市场信号质量不足。",
    summary.mistakeCount
      ? "- 今日存在执行错误或授权/API问题，已记录在操作日志，不能用缺失数据补交易。"
      : "- 今日执行层没有记录错误。",
    "",
    "## 不可篡改原则",
    "",
    "- 本报告只汇总账本已有扫描、决策、成交、错误和资金快照。",
    "- API失败、离线、授权失效都按失败记录处理，不补数据、不虚构成交。"
  ];
  return `${lines.join("\n")}\n`;
}

const ledger = await readJson(LEDGER_FILE);
const days = [...new Set((ledger.runs || []).map((run) => dayKey(run.startedAt)))].sort().reverse();
const summaries = days.map((day) => summarizeDay(day, ledger));
const latest = summaries[0] || summarizeDay(dayKey(new Date()), ledger);
const operationLog = {
  schemaVersion: 1,
  generatedAt: new Date().toISOString(),
  source: LEDGER_FILE,
  totalRuns: (ledger.runs || []).length,
  latestRunId: (ledger.runs || [])[0]?.id || "",
  entries: (ledger.runs || []).map((run) => runToOperation(run))
};

await mkdir("docs/data", { recursive: true });
await mkdir(REPORT_DIR, { recursive: true });
await writeFile(OPERATION_LOG_FILE, `${JSON.stringify(operationLog, null, 2)}\n`, "utf8");
await writeFile(SUMMARY_FILE, `${JSON.stringify({ schemaVersion: 1, generatedAt: new Date().toISOString(), latest, summaries }, null, 2)}\n`, "utf8");
await writeFile(`${REPORT_DIR}/${latest.date}-strategy-summary.md`, markdown(latest), "utf8");
await writeFile(`${REPORT_DIR}/latest-strategy-summary.md`, markdown(latest), "utf8");

console.log(`Wrote ${OPERATION_LOG_FILE}`);
console.log(`Wrote ${SUMMARY_FILE}`);
console.log(`Wrote ${REPORT_DIR}/${latest.date}-strategy-summary.md`);
