const requiredFiles = [
  "README.md",
  ".env.example",
  "docs/PROJECT_BRIEF.md",
  "docs/PROJECT_MEMORY.md",
  "docs/MEME_STRATEGY.md",
  "docs/index.html",
  "docs/data/meme.json",
  "docs/DATA_INTEGRATION_MATRIX.md",
  "docs/HUMMINGBOT_EXECUTION_PLAN.md",
  "docs/RISK_CONTROL.md"
];

const requiredEnvKeys = [
  "OKX_API_KEY",
  "OKX_SECRET_KEY",
  "OKX_PASSPHRASE",
  "PRIMARY_WALLET_ADDRESS",
  "EVM_RPC_URL"
];

async function fileExists(path) {
  const fs = await import("node:fs/promises");

  try {
    await fs.access(path);
    return true;
  } catch {
    return false;
  }
}

const missingFiles = [];

for (const file of requiredFiles) {
  if (!(await fileExists(file))) {
    missingFiles.push(file);
  }
}

if (missingFiles.length > 0) {
  console.error("Missing project files:");
  for (const file of missingFiles) {
    console.error(`- ${file}`);
  }
  process.exit(1);
}

console.log("Project scaffold: OK");
console.log("Expected env keys:");
for (const key of requiredEnvKeys) {
  console.log(`- ${key}`);
}
