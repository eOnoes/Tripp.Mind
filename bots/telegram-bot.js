"use strict";

const TelegramBot = require("node-telegram-bot-api");

const { GatewayClient } = require("../lib/gateway-client");
const { HELP_TEXT, formatGraph, formatRecent, formatRemember, formatSearch, truncate } = require("../lib/bot-format");
const { createLogger } = require("../lib/logger");

const logger = createLogger("telegram-bot");

const token = process.env.TELEGRAM_BOT_TOKEN;
if (!token) {
  throw new Error("TELEGRAM_BOT_TOKEN is required");
}

const allowedChatIds = parseAllowedIds(process.env.TELEGRAM_ALLOWED_CHAT_IDS || "");
const client = new GatewayClient();
const bot = new TelegramBot(token, { polling: true });

bot.onText(/^\/remember(?:@\w+)?(?:\s+([\s\S]+))?$/i, async (msg, match) => {
  await guarded(msg, async () => {
    const text = match && match[1] ? match[1].trim() : "";
    if (!text) {
      return send(msg.chat.id, "Usage: /remember <text>");
    }
    const note = await client.createNoteFromText(text);
    return send(msg.chat.id, formatRemember(note));
  });
});

bot.onText(/^\/search(?:@\w+)?(?:\s+([\s\S]+))?$/i, async (msg, match) => {
  await guarded(msg, async () => {
    const query = match && match[1] ? match[1].trim() : "";
    if (!query) {
      return send(msg.chat.id, "Usage: /search <query>");
    }
    const result = await client.search(query);
    return send(msg.chat.id, formatSearch(result));
  });
});

bot.onText(/^\/graph(?:@\w+)?$/i, async (msg) => {
  await guarded(msg, async () => send(msg.chat.id, formatGraph(await client.graphStats())));
});

bot.onText(/^\/recent(?:@\w+)?$/i, async (msg) => {
  await guarded(msg, async () => send(msg.chat.id, formatRecent(await client.recentNotes())));
});

bot.onText(/^\/help(?:@\w+)?$/i, async (msg) => {
  await guarded(msg, async () => send(msg.chat.id, HELP_TEXT));
});

bot.on("polling_error", (error) => {
  logger.error("polling error", { message: error.message });
});

logger.info("telegram bot started");

async function guarded(msg, handler) {
  if (!authorized(msg.chat.id)) {
    logger.warn("blocked unauthorized chat", { chatId: msg.chat.id });
    return;
  }

  try {
    await handler();
  } catch (error) {
    logger.error("command failed", { message: error.message });
    await send(msg.chat.id, `Error: ${error.message}`);
  }
}

function authorized(chatId) {
  return allowedChatIds.size === 0 || allowedChatIds.has(String(chatId));
}

async function send(chatId, text) {
  await bot.sendMessage(chatId, truncate(text, 3900), { disable_web_page_preview: true });
}

function parseAllowedIds(value) {
  return new Set(value.split(",").map((item) => item.trim()).filter(Boolean));
}

async function shutdown() {
  logger.info("shutting down");
  await bot.stopPolling();
  process.exit(0);
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
