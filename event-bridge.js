"use strict";

const http = require("http");
const { URL } = require("url");
const WebSocket = require("ws");

const { createLogger } = require("./lib/logger");

const logger = createLogger("event-bridge");

const port = Number(process.env.EVENT_BRIDGE_PORT || process.env.PORT || 3010);
const siyuanBaseUrl = (process.env.SIYUAN_BASE_URL || "http://siyuan:6806").replace(/\/+$/, "");
const siyuanAccessAuthCode = process.env.SIYUAN_ACCESS_AUTH_CODE || "";
const siyuanXAuthToken = process.env.SIYUAN_X_AUTH_TOKEN || "";
const clientAuthToken = process.env.EVENT_BRIDGE_AUTH_TOKEN || "";
const reconnectMinMs = Number(process.env.EVENT_BRIDGE_RECONNECT_MIN_MS || 1000);
const reconnectMaxMs = Number(process.env.EVENT_BRIDGE_RECONNECT_MAX_MS || 30000);
const heartbeatMs = Number(process.env.EVENT_BRIDGE_HEARTBEAT_MS || 30000);
const includeRaw = /^true$/i.test(process.env.EVENT_BRIDGE_INCLUDE_RAW || "");

let upstream = null;
let upstreamConnected = false;
let reconnectAttempt = 0;
let reconnectTimer = null;
let upstreamCookie = "";
let lastUpstreamEventAt = null;

const server = http.createServer((req, res) => {
  if (req.url === "/health") {
    res.writeHead(upstreamConnected ? 200 : 503, { "Content-Type": "application/json" });
    res.end(JSON.stringify({
      status: upstreamConnected ? "ok" : "degraded",
      service: "tripp-mind-event-bridge",
      clients: wss.clients.size,
      upstreamConnected,
      lastUpstreamEventAt
    }));
    return;
  }

  res.writeHead(404, { "Content-Type": "application/json" });
  res.end(JSON.stringify({ error: "not_found" }));
});

const wss = new WebSocket.Server({ server });

wss.on("connection", (socket, req) => {
  if (!clientAuthorized(req)) {
    socket.close(1008, "unauthorized");
    return;
  }

  socket.isAlive = true;
  socket.on("pong", () => {
    socket.isAlive = true;
  });

  send(socket, {
    type: "bridge_status",
    timestamp: new Date().toISOString(),
    payload: {
      upstreamConnected,
      lastUpstreamEventAt
    }
  });

  logger.info("client connected", { clients: wss.clients.size });
});

function start() {
  setInterval(() => {
    for (const socket of wss.clients) {
      if (socket.isAlive === false) {
        socket.terminate();
        continue;
      }
      socket.isAlive = false;
      socket.ping();
    }

    if (upstream && upstream.readyState === WebSocket.OPEN) {
      upstream.ping();
    }
  }, heartbeatMs).unref();

  server.listen(port, () => {
    logger.info("event bridge listening", { port, siyuanBaseUrl });
    connectUpstream();
  });
}

async function connectUpstream() {
  clearTimeout(reconnectTimer);

  try {
    const headers = await upstreamHeaders();
    const wsUrl = buildSiyuanWsUrl();
    logger.info("connecting to SiYuan websocket", { wsUrl });

    upstream = new WebSocket(wsUrl, { headers, handshakeTimeout: 15000 });
    upstream.on("open", handleUpstreamOpen);
    upstream.on("message", handleUpstreamMessage);
    upstream.on("close", (code, reason) => handleUpstreamClose(code, reason.toString()));
    upstream.on("error", (error) => logger.warn("upstream websocket error", { message: error.message }));
    upstream.on("pong", () => {
      upstreamConnected = true;
    });
  } catch (error) {
    logger.error("failed to prepare upstream websocket", { message: error.message });
    scheduleReconnect();
  }
}

function handleUpstreamOpen() {
  reconnectAttempt = 0;
  upstreamConnected = true;
  logger.info("connected to SiYuan websocket");
  broadcast({
    type: "bridge_status",
    timestamp: new Date().toISOString(),
    payload: { upstreamConnected: true }
  });
}

function handleUpstreamClose(code, reason) {
  upstreamConnected = false;
  logger.warn("SiYuan websocket closed", { code, reason });
  broadcast({
    type: "bridge_status",
    timestamp: new Date().toISOString(),
    payload: { upstreamConnected: false, code, reason }
  });
  scheduleReconnect();
}

function handleUpstreamMessage(message) {
  let raw;
  try {
    raw = JSON.parse(message.toString());
  } catch (error) {
    logger.warn("ignored non-json upstream message", { message: message.toString().slice(0, 200) });
    return;
  }

  lastUpstreamEventAt = new Date().toISOString();
  for (const event of normalizeEvent(raw)) {
    broadcast(event);
  }
}

function normalizeEvent(raw) {
  const cmd = raw.cmd;
  const data = raw.data || {};
  const timestamp = new Date().toISOString();
  const events = [];

  if (cmd === "create") {
    events.push(event("note_created", timestamp, {
      notebook: data.box && data.box.id,
      notebookName: data.box && data.box.name,
      path: data.path,
      listDocTree: data.listDocTree
    }, raw));
  } else if (cmd === "savedoc") {
    events.push(event("note_updated", timestamp, {
      id: data.rootID,
      updateType: data.type,
      sources: data.sources
    }, raw));
  } else if (cmd === "removeDoc") {
    const ids = Array.isArray(data.ids) ? data.ids : [];
    for (const id of ids) {
      events.push(event("note_deleted", timestamp, {
        id,
        notebook: data.box,
        path: data.path
      }, raw));
    }
  } else if (cmd === "createnotebook") {
    events.push(event("notebook_created", timestamp, {
      notebook: data.box && data.box.id,
      name: data.box && data.box.name,
      existed: data.existed
    }, raw));
  } else if (cmd === "transactions") {
    for (const operation of transactionOperations(data)) {
      const action = operation.action || operation.Action;
      if (["insert", "appendInsert", "prependInsert"].includes(action)) {
        events.push(event("note_updated", timestamp, {
          id: operation.id || operation.ID,
          action
        }, raw));
      } else if (["update", "delete", "move"].includes(action)) {
        events.push(event("note_updated", timestamp, {
          id: operation.id || operation.ID,
          action
        }, raw));
      }
    }
  }

  return events;
}

function transactionOperations(data) {
  const transactions = Array.isArray(data) ? data : [];
  const operations = [];
  for (const tx of transactions) {
    const doOperations = tx.doOperations || tx.DoOperations || [];
    if (Array.isArray(doOperations)) {
      operations.push(...doOperations);
    }
  }
  return operations;
}

function event(type, timestamp, payload, raw) {
  const normalized = {
    type,
    id: `${type}-${Date.now()}-${Math.random().toString(16).slice(2)}`,
    source: "siyuan",
    timestamp,
    payload
  };

  if (includeRaw) {
    normalized.raw = raw;
  }

  return normalized;
}

async function upstreamHeaders() {
  const headers = {};

  if (siyuanXAuthToken) {
    headers["X-Auth-Token"] = siyuanXAuthToken;
    return headers;
  }

  if (siyuanAccessAuthCode) {
    if (!upstreamCookie) {
      upstreamCookie = await loginCookie();
    }
    headers.Cookie = upstreamCookie;
  }

  return headers;
}

async function loginCookie() {
  const response = await fetch(`${siyuanBaseUrl}/api/system/loginAuth`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ authCode: siyuanAccessAuthCode, rememberMe: true })
  });

  const body = await response.json().catch(() => ({}));
  if (!response.ok || Number(body.code || 0) !== 0) {
    throw new Error(body.msg || `SiYuan login failed with HTTP ${response.status}`);
  }

  const setCookies = typeof response.headers.getSetCookie === "function"
    ? response.headers.getSetCookie()
    : [response.headers.get("set-cookie")].filter(Boolean);

  const cookie = setCookies.map((value) => value.split(";")[0]).join("; ");
  if (!cookie) {
    throw new Error("SiYuan login did not return a session cookie");
  }

  logger.info("authenticated to SiYuan websocket with login cookie");
  return cookie;
}

function buildSiyuanWsUrl() {
  const url = new URL(siyuanBaseUrl);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  url.pathname = "/ws";
  url.searchParams.set("app", "tripp-mind-event-bridge");
  url.searchParams.set("id", `fleet-${process.pid}`);
  url.searchParams.set("type", "main");
  return url.toString();
}

function scheduleReconnect() {
  clearTimeout(reconnectTimer);
  reconnectAttempt += 1;
  const delay = Math.min(reconnectMaxMs, reconnectMinMs * (2 ** Math.min(reconnectAttempt, 8)));
  reconnectTimer = setTimeout(connectUpstream, delay);
  logger.info("scheduled upstream reconnect", { delayMs: delay, attempt: reconnectAttempt });
}

function clientAuthorized(req) {
  if (!clientAuthToken) {
    return true;
  }

  const url = new URL(req.url, "http://localhost");
  const queryToken = url.searchParams.get("token");
  const authHeader = req.headers.authorization || "";
  const bearer = authHeader.match(/^Bearer\s+(.+)$/i);
  return queryToken === clientAuthToken || (bearer && bearer[1] === clientAuthToken);
}

function broadcast(payload) {
  const encoded = JSON.stringify(payload);
  for (const client of wss.clients) {
    if (client.readyState === WebSocket.OPEN) {
      client.send(encoded);
    }
  }
}

function send(socket, payload) {
  if (socket.readyState === WebSocket.OPEN) {
    socket.send(JSON.stringify(payload));
  }
}

function shutdown() {
  logger.info("shutting down");
  clearTimeout(reconnectTimer);
  if (upstream) {
    upstream.close();
  }
  wss.close();
  server.close(() => process.exit(0));
}

if (require.main === module && process.env.TRIPP_MIND_TEST_MODE !== "1") {
  start();
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);
}

module.exports = {
  buildSiyuanWsUrl,
  clientAuthorized,
  normalizeEvent,
  start,
  transactionOperations
};
