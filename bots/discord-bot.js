"use strict";

const {
  Client,
  GatewayIntentBits,
  REST,
  Routes,
  SlashCommandBuilder
} = require("discord.js");

const { GatewayClient } = require("../lib/gateway-client");
const { HELP_TEXT, formatGraph, formatRecent, formatRemember, formatSearch, truncate } = require("../lib/bot-format");
const { createLogger } = require("../lib/logger");

const logger = createLogger("discord-bot");

const token = process.env.DISCORD_BOT_TOKEN;
const applicationId = process.env.DISCORD_APPLICATION_ID;
const guildId = process.env.DISCORD_GUILD_ID || "";

if (!token) {
  throw new Error("DISCORD_BOT_TOKEN is required");
}
if (!applicationId) {
  throw new Error("DISCORD_APPLICATION_ID is required");
}

const gateway = new GatewayClient();
const discord = new Client({ intents: [GatewayIntentBits.Guilds] });

const commands = [
  new SlashCommandBuilder()
    .setName("remember")
    .setDescription("Save a note")
    .addStringOption((option) => option.setName("text").setDescription("Note text").setRequired(true)),
  new SlashCommandBuilder()
    .setName("search")
    .setDescription("Search notes")
    .addStringOption((option) => option.setName("query").setDescription("Search query").setRequired(true)),
  new SlashCommandBuilder().setName("graph").setDescription("Show knowledge graph stats"),
  new SlashCommandBuilder().setName("recent").setDescription("Show recent notes"),
  new SlashCommandBuilder().setName("help").setDescription("List commands")
].map((command) => command.toJSON());

discord.once("ready", () => {
  logger.info("discord bot started", { user: discord.user && discord.user.tag });
});

discord.on("interactionCreate", async (interaction) => {
  if (!interaction.isChatInputCommand()) {
    return;
  }

  try {
    await interaction.deferReply();
    const response = await runCommand(interaction);
    await interaction.editReply(truncate(response, 1900));
  } catch (error) {
    logger.error("command failed", { command: interaction.commandName, message: error.message });
    const response = `Error: ${error.message}`;
    if (interaction.deferred || interaction.replied) {
      await interaction.editReply(truncate(response, 1900));
    } else {
      await interaction.reply({ content: truncate(response, 1900), ephemeral: true });
    }
  }
});

registerCommands()
  .then(() => discord.login(token))
  .catch((error) => {
    logger.error("startup failed", { message: error.message });
    process.exit(1);
  });

async function runCommand(interaction) {
  switch (interaction.commandName) {
    case "remember": {
      const note = await gateway.createNoteFromText(interaction.options.getString("text", true));
      return formatRemember(note);
    }
    case "search": {
      const result = await gateway.search(interaction.options.getString("query", true));
      return formatSearch(result);
    }
    case "graph":
      return formatGraph(await gateway.graphStats());
    case "recent":
      return formatRecent(await gateway.recentNotes());
    case "help":
      return HELP_TEXT;
    default:
      return "Unknown command.";
  }
}

async function registerCommands() {
  const rest = new REST({ version: "10" }).setToken(token);
  if (guildId) {
    await rest.put(Routes.applicationGuildCommands(applicationId, guildId), { body: commands });
    logger.info("registered guild slash commands", { guildId });
  } else {
    await rest.put(Routes.applicationCommands(applicationId), { body: commands });
    logger.info("registered global slash commands");
  }
}

function shutdown() {
  logger.info("shutting down");
  discord.destroy();
  process.exit(0);
}

process.on("SIGINT", shutdown);
process.on("SIGTERM", shutdown);
