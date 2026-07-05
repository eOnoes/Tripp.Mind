"use strict";

const express = require("express");
const rateLimit = require("express-rate-limit");
const jwt = require("jsonwebtoken");
const morgan = require("morgan");
const { createProxyMiddleware } = require("http-proxy-middleware");

const app = express();

const port = Number(process.env.PORT || 3000);
const siyuanBaseUrl = process.env.SIYUAN_BASE_URL || "http://siyuan:6806";
const siyuanApiToken = process.env.SIYUAN_API_TOKEN || "";
const jwtSecret = process.env.JWT_SECRET;
const jwtIssuer = process.env.JWT_ISSUER || undefined;
const jwtAudience = process.env.JWT_AUDIENCE || undefined;
const dashboardCorsOrigin = process.env.DASHBOARD_CORS_ORIGIN || "";

if (!jwtSecret) {
  throw new Error("JWT_SECRET is required");
}

const rateLimitWindowMs = Number(process.env.RATE_LIMIT_WINDOW_MS || 60000);
const rateLimitMax = Number(process.env.RATE_LIMIT_MAX || 100);

const roleAllowlist = {
  reader: [
    { methods: ["GET"], path: /^\/$/ },
    { methods: ["GET"], path: /^\/(appearance|assets|stage)\/.*$/ },
    { methods: ["POST"], path: /^\/api\/system\/(bootProgress|version|currentTime|getEmojiConf|getConf)$/ },
    { methods: ["POST"], path: /^\/api\/notebook\/(lsNotebooks|getNotebookConf)$/ },
    { methods: ["POST"], path: /^\/api\/storage\/getRecentDocs$/ },
    { methods: ["POST"], path: /^\/api\/filetree\/(listDocsByPath|getDoc|searchDocs|getHPathByPath|getHPathByID|getPathByID|getIDsByHPath)$/ },
    { methods: ["POST"], path: /^\/api\/block\/(getBlockInfo|getBlockKramdown|getChildBlocks)$/ },
    { methods: ["POST"], path: /^\/api\/attr\/getBlockAttrs$/ },
    { methods: ["POST"], path: /^\/api\/search\/(searchBlock|fullTextSearchBlock)$/ },
    { methods: ["POST"], path: /^\/api\/graph\/getGraph$/ },
    { methods: ["POST"], path: /^\/api\/query\/sql$/ }
  ],
  writer: [
    { methods: ["POST"], path: /^\/api\/block\/(insertBlock|prependBlock|appendBlock|updateBlock|deleteBlock|moveBlock|foldBlock|unfoldBlock|transferBlockRef)$/ },
    { methods: ["POST"], path: /^\/api\/filetree\/(createDocWithMd|renameDoc|removeDoc|removeDocByID|moveDocs|createDoc|createDailyNote|duplicateDoc)$/ },
    { methods: ["POST"], path: /^\/api\/notebook\/(createNotebook|renameNotebook|setNotebookConf|changeSortNotebook|setNotebookIcon)$/ },
    { methods: ["POST"], path: /^\/api\/attr\/setBlockAttrs$/ },
    { methods: ["POST"], path: /^\/api\/transactions$/ }
  ],
  backup: [
    { methods: ["POST"], path: /^\/api\/repo\/(createSnapshot|getRepoSnapshots)$/ },
    { methods: ["POST"], path: /^\/api\/export\/exportData$/ },
    { methods: ["GET"], path: /^\/export\/.*$/ }
  ],
  admin: [
    { methods: ["*"], path: /^\/.*$/ }
  ]
};

roleAllowlist.writer = [...roleAllowlist.reader, ...roleAllowlist.writer];
roleAllowlist.backup = [...roleAllowlist.reader, ...roleAllowlist.backup];

app.disable("x-powered-by");
app.set("trust proxy", 1);
app.use(morgan("combined"));

if (dashboardCorsOrigin) {
  app.use((req, res, next) => {
    res.setHeader("Access-Control-Allow-Origin", dashboardCorsOrigin);
    res.setHeader("Access-Control-Allow-Headers", "Authorization, Content-Type");
    res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
    if (req.method === "OPTIONS") {
      return res.sendStatus(204);
    }
    return next();
  });
}

app.get("/api/health", (req, res) => {
  res.json({
    status: "ok",
    service: "siyuan-api-gateway",
    siyuanBaseUrl
  });
});

app.use(rateLimit({
  windowMs: rateLimitWindowMs,
  max: rateLimitMax,
  standardHeaders: true,
  legacyHeaders: false
}));

function validateJwt(req, res, next) {
  const authHeader = req.get("authorization") || "";
  const match = authHeader.match(/^Bearer\s+(.+)$/i);

  if (!match) {
    return res.status(401).json({ error: "missing_bearer_token" });
  }

  try {
    req.user = jwt.verify(match[1], jwtSecret, {
      issuer: jwtIssuer,
      audience: jwtAudience
    });
    return next();
  } catch (error) {
    return res.status(401).json({ error: "invalid_token" });
  }
}

function getRoles(payload) {
  const roles = new Set();

  if (typeof payload.role === "string") {
    roles.add(payload.role.toLowerCase());
  }

  if (Array.isArray(payload.roles)) {
    for (const role of payload.roles) {
      if (typeof role === "string") {
        roles.add(role.toLowerCase());
      }
    }
  }

  return [...roles];
}

function authorizeByRole(req, res, next) {
  const roles = getRoles(req.user || {});
  const method = req.method.toUpperCase();
  const path = req.path;

  const allowed = roles.some((role) => {
    const rules = roleAllowlist[role] || [];
    return rules.some((rule) => {
      const methodAllowed = rule.methods.includes("*") || rule.methods.includes(method);
      return methodAllowed && rule.path.test(path);
    });
  });

  if (!allowed) {
    return res.status(403).json({
      error: "endpoint_not_allowed",
      method,
      path,
      roles
    });
  }

  return next();
}

const siyuanProxy = createProxyMiddleware({
  target: siyuanBaseUrl,
  changeOrigin: true,
  xfwd: true,
  proxyTimeout: 30000,
  timeout: 30000,
  logLevel: "warn",
  onProxyReq: (proxyReq) => {
    proxyReq.removeHeader("authorization");

    if (siyuanApiToken) {
      proxyReq.setHeader("Authorization", `Token ${siyuanApiToken}`);
    }
  },
  onError: (error, req, res) => {
    if (!res.headersSent) {
      res.status(502).json({
        error: "siyuan_proxy_error",
        message: error.message
      });
    }
  }
});

app.use(validateJwt, authorizeByRole, siyuanProxy);

app.listen(port, () => {
  console.log(`SiYuan API gateway listening on port ${port}`);
});
