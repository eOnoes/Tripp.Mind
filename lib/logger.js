"use strict";

function createLogger(service) {
  function write(level, message, meta = undefined) {
    const entry = {
      level,
      service,
      message,
      time: new Date().toISOString()
    };

    if (meta !== undefined) {
      entry.meta = meta;
    }

    const line = JSON.stringify(entry);
    if (level === "error") {
      console.error(line);
    } else if (level === "warn") {
      console.warn(line);
    } else {
      console.log(line);
    }
  }

  return {
    info: (message, meta) => write("info", message, meta),
    warn: (message, meta) => write("warn", message, meta),
    error: (message, meta) => write("error", message, meta)
  };
}

module.exports = { createLogger };
