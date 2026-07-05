"use strict";

const fs = require("fs/promises");
const path = require("path");
const cron = require("node-cron");

const { GatewayClient } = require("./lib/gateway-client");
const { createLogger } = require("./lib/logger");

const logger = createLogger("backup-service");

const backupDir = process.env.BACKUP_DIR || "/backups";
const cronSchedule = process.env.BACKUP_CRON_SCHEDULE || process.env.BACKUP_CRON || "0 2 * * *";
const runOnStartup = !/^false$/i.test(process.env.BACKUP_RUN_ON_STARTUP || "true");
const retentionCount = Number(process.env.BACKUP_RETENTION_COUNT || 14);
let client = null;

let running = false;

async function runBackup(reason = "scheduled") {
  if (running) {
    logger.warn("backup already running, skipping", { reason });
    return;
  }

  running = true;
  const startedAt = new Date();
  const timestamp = startedAt.toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
  const fileName = `tripp-mind-${timestamp}.zip`;
  const filePath = path.join(backupDir, fileName);

  try {
    await fs.mkdir(backupDir, { recursive: true });
    logger.info("backup started", { reason, fileName });

    const gateway = getClient();
    await gateway.createSnapshot(`Tripp.Mind backup ${startedAt.toISOString()}`);
    const exported = await gateway.exportData();
    const exportPath = exported && exported.zip;
    if (!exportPath) {
      throw new Error("SiYuan exportData did not return a zip path");
    }

    await client.downloadToFile(exportPath, filePath);
    await pruneOldBackups();

    logger.info("backup completed", {
      fileName,
      elapsedMs: Date.now() - startedAt.getTime()
    });
  } catch (error) {
    logger.error("backup failed", {
      fileName,
      message: error.message
    });
  } finally {
    running = false;
  }
}

function getClient() {
  if (!client) {
    client = new GatewayClient();
  }
  return client;
}

async function pruneOldBackups() {
  if (!Number.isFinite(retentionCount) || retentionCount <= 0) {
    return;
  }

  const entries = await fs.readdir(backupDir, { withFileTypes: true });
  const backups = entries
    .filter((entry) => entry.isFile() && /^tripp-mind-\d{8}T\d{6}Z\.zip$/.test(entry.name))
    .map((entry) => entry.name)
    .sort()
    .reverse();

  for (const oldBackup of backups.slice(retentionCount)) {
    await fs.unlink(path.join(backupDir, oldBackup));
    logger.info("removed old backup", { fileName: oldBackup });
  }
}

function start() {
  if (!cron.validate(cronSchedule)) {
    throw new Error(`Invalid BACKUP_CRON_SCHEDULE expression: ${cronSchedule}`);
  }

  cron.schedule(cronSchedule, () => {
    runBackup("cron").catch((error) => logger.error("unexpected backup error", { message: error.message }));
  });

  logger.info("backup service scheduled", { cronSchedule, backupDir, retentionCount });

  if (runOnStartup) {
    runBackup("startup").catch((error) => logger.error("unexpected startup backup error", { message: error.message }));
  }

  process.on("SIGINT", () => process.exit(0));
  process.on("SIGTERM", () => process.exit(0));
}

if (require.main === module && process.env.TRIPP_MIND_TEST_MODE !== "1") {
  start();
}

module.exports = {
  pruneOldBackups,
  runBackup,
  start
};
