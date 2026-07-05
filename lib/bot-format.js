"use strict";

const HELP_TEXT = [
  "/remember <text> - save a note",
  "/search <query> - search notes",
  "/graph - show knowledge graph stats",
  "/recent - show recent notes",
  "/help - list commands"
].join("\n");

function formatRemember(note) {
  return `Saved: ${note.title}\nID: ${note.id || "unknown"}`;
}

function formatSearch(result) {
  const blocks = Array.isArray(result && result.blocks) ? result.blocks : [];
  if (blocks.length === 0) {
    return "No matching notes found.";
  }

  const lines = blocks.slice(0, 5).map((block, index) => {
    const title = clean(block.hPath || block.name || block.content || block.markdown || block.id || "Untitled");
    const preview = clean(block.content || block.markdown || block.fcontent || "").slice(0, 180);
    return `${index + 1}. ${title}${preview && preview !== title ? `\n   ${preview}` : ""}`;
  });

  const total = Number(result.matchedBlockCount || blocks.length);
  return `Found ${total} matching block${total === 1 ? "" : "s"}:\n\n${lines.join("\n\n")}`;
}

function formatGraph(stats) {
  return [
    "Knowledge graph",
    `Notes/nodes: ${stats.nodes}`,
    `Links: ${stats.links}`,
    stats.notebook ? `Notebook: ${stats.notebook}` : ""
  ].filter(Boolean).join("\n");
}

function formatRecent(docs) {
  if (!Array.isArray(docs) || docs.length === 0) {
    return "No recent notes found.";
  }

  return docs.map((doc, index) => {
    const title = clean(doc.hPath || doc.title || doc.name || doc.rootID || doc.id || "Untitled");
    const updated = doc.updated || doc.opened || doc.closed || "";
    return `${index + 1}. ${title}${updated ? `\n   ${updated}` : ""}`;
  }).join("\n\n");
}

function clean(value) {
  return String(value || "")
    .replace(/<[^>]+>/g, "")
    .replace(/&nbsp;/g, " ")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">")
    .replace(/&amp;/g, "&")
    .replace(/\s+/g, " ")
    .trim();
}

function truncate(value, maxLength) {
  const text = String(value || "");
  if (text.length <= maxLength) {
    return text;
  }
  return `${text.slice(0, Math.max(0, maxLength - 20))}\n... truncated ...`;
}

module.exports = {
  HELP_TEXT,
  formatGraph,
  formatRecent,
  formatRemember,
  formatSearch,
  truncate
};
