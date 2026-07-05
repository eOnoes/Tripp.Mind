"use strict";

const fs = require("fs");
const { Readable } = require("stream");
const { pipeline } = require("stream/promises");

class GatewayClient {
  constructor(options = {}) {
    this.baseUrl = (options.baseUrl || process.env.SIYUAN_GATEWAY_URL || "http://gateway:3000").replace(/\/+$/, "");
    this.token = options.token || process.env.SIYUAN_GATEWAY_TOKEN || process.env.SIYUAN_GATEWAY_JWT || "";
    this.defaultNotebook = options.defaultNotebook || process.env.SIYUAN_DEFAULT_NOTEBOOK || "";
    this.timeoutMs = Number(options.timeoutMs || process.env.SIYUAN_GATEWAY_TIMEOUT_MS || 30000);
    this.retries = Number(options.retries || process.env.SIYUAN_GATEWAY_RETRIES || 2);

    if (!this.token) {
      throw new Error("SIYUAN_GATEWAY_TOKEN is required");
    }
  }

  async post(path, payload = {}) {
    return this.request("POST", path, { json: payload });
  }

  async request(method, path, options = {}) {
    const url = this.url(path);
    let lastError;

    for (let attempt = 0; attempt <= this.retries; attempt += 1) {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), this.timeoutMs);

      try {
        const headers = {
          Accept: "application/json",
          Authorization: `Bearer ${this.token}`
        };
        const requestOptions = {
          method,
          headers,
          signal: controller.signal
        };

        if (options.json !== undefined) {
          headers["Content-Type"] = "application/json";
          requestOptions.body = JSON.stringify(options.json);
        }

        const response = await fetch(url, requestOptions);
        if (response.status >= 500 && attempt < this.retries) {
          await this.sleep(attempt, response);
          continue;
        }

        return await this.handleResponse(response);
      } catch (error) {
        lastError = error;
        if (attempt < this.retries) {
          await this.sleep(attempt);
          continue;
        }
        throw error;
      } finally {
        clearTimeout(timeout);
      }
    }

    throw lastError || new Error(`Request failed: ${method} ${url}`);
  }

  async downloadToFile(path, filePath) {
    const response = await fetch(this.url(path), {
      headers: {
        Authorization: `Bearer ${this.token}`
      }
    });

    if (!response.ok) {
      const text = await response.text();
      throw new Error(`Download failed with HTTP ${response.status}: ${text.slice(0, 300)}`);
    }

    await pipeline(Readable.fromWeb(response.body), fs.createWriteStream(filePath, { flags: "wx" }));
  }

  async listNotebooks() {
    const data = await this.post("/api/notebook/lsNotebooks", {});
    const notebooks = data && Array.isArray(data.notebooks) ? data.notebooks : [];
    return notebooks.filter((notebook) => notebook && !notebook.closed);
  }

  async resolveNotebook() {
    if (this.defaultNotebook) {
      return this.defaultNotebook;
    }

    const notebooks = await this.listNotebooks();
    if (notebooks.length === 0) {
      throw new Error("No open SiYuan notebooks found. Set SIYUAN_DEFAULT_NOTEBOOK.");
    }

    return notebooks[0].id;
  }

  async createNoteFromText(text) {
    const content = String(text || "").trim();
    if (!content) {
      throw new Error("Note text is required");
    }

    const notebook = await this.resolveNotebook();
    const title = titleFromText(content);
    const timestamp = timestampForPath();
    const path = `/${slugify(title)}-${timestamp}`;
    const markdown = content.startsWith("# ") ? content : `# ${title}\n\n${content}`;
    const id = await this.post("/api/filetree/createDocWithMd", {
      notebook,
      path,
      markdown
    });

    return {
      id: String(id || ""),
      notebook,
      title,
      path
    };
  }

  async search(query, pageSize = 5) {
    return this.post("/api/search/fullTextSearchBlock", {
      query,
      page: 1,
      pageSize,
      paths: [],
      boxes: [],
      types: {},
      subTypes: {},
      method: 0,
      orderBy: 0,
      groupBy: 0
    });
  }

  async graphStats() {
    const data = await this.post("/api/graph/getGraph", {
      k: "",
      conf: {},
      reqId: `fleet-${Date.now()}`
    });

    return {
      nodes: Array.isArray(data.nodes) ? data.nodes.length : 0,
      links: Array.isArray(data.links) ? data.links.length : 0,
      notebook: data.box || ""
    };
  }

  async recentNotes(limit = 5) {
    const data = await this.post("/api/storage/getRecentDocs", { sortBy: "updated" });
    const docs = Array.isArray(data) ? data : [];
    return docs.slice(0, limit);
  }

  async createSnapshot(memo) {
    return this.post("/api/repo/createSnapshot", { memo });
  }

  async exportData() {
    return this.post("/api/export/exportData", {});
  }

  async handleResponse(response) {
    const text = await response.text();
    let body = text;
    if (text) {
      try {
        body = JSON.parse(text);
      } catch {
        body = text;
      }
    }

    if (!response.ok) {
      const message = body && typeof body === "object" ? body.message || body.msg || body.error : body;
      throw new Error(`HTTP ${response.status}: ${message || response.statusText}`);
    }

    if (body && typeof body === "object" && Object.prototype.hasOwnProperty.call(body, "code")) {
      if (Number(body.code) !== 0) {
        throw new Error(body.msg || `SiYuan API error ${body.code}`);
      }
      return body.data;
    }

    return body;
  }

  url(path) {
    if (/^https?:\/\//i.test(path)) {
      return path;
    }
    return `${this.baseUrl}/${String(path).replace(/^\/+/, "")}`;
  }

  async sleep(attempt, response = undefined) {
    const retryAfter = response ? Number(response.headers.get("retry-after")) : NaN;
    const delayMs = Number.isFinite(retryAfter) ? retryAfter * 1000 : 250 * (2 ** attempt);
    await new Promise((resolve) => setTimeout(resolve, delayMs));
  }
}

function titleFromText(text) {
  const firstLine = text.split(/\r?\n/).find((line) => line.trim()) || "Memory";
  return firstLine.replace(/^#+\s*/, "").trim().slice(0, 80) || "Memory";
}

function slugify(value) {
  return value
    .toLowerCase()
    .replace(/[^a-z0-9\s_-]/g, "")
    .trim()
    .replace(/[\s_-]+/g, "-")
    .slice(0, 60) || "memory";
}

function timestampForPath() {
  return new Date().toISOString().replace(/[-:]/g, "").replace(/\.\d{3}Z$/, "Z");
}

module.exports = { GatewayClient };
