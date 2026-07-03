#!/usr/bin/env node
"use strict";
//node mcp-client.js --node ..\..\servers\biome-mcp-server\dist\biome-mcp-server.js
//node mcp-client.js --node ..\..\servers\fast-filesystem-mcp\dist\index.js
//node mcp-client.js --node ..\..\servers\codebase-mcp\dist\cli.js start

const { spawn } = require("child_process");
const readline = require("readline");
const http = require("http");
const https = require("https");
const { URL } = require("url");
const fs = require("fs");
const path = require("path");

function parseArgs(argv) {
  const args = argv.slice(2);
  const opts = { transport: null, command: null, commandArgs: [], url: null, auth: null, output: null };

  let i = 0;
  while (i < args.length) {
    const a = args[i];
    if (a === "--node") {
      opts.transport = "stdio";
      opts.command = "node";
      opts.commandArgs = args.slice(i + 1);
      break;
    } else if (a === "--npx") {
      opts.transport = "stdio";
      opts.command = "npx";
      opts.commandArgs = args.slice(i + 1);
      break;
    } else if (a === "--python" || a === "--python3") {
      opts.transport = "stdio";
      opts.command = a === "--python3" ? "python3" : "python";
      opts.commandArgs = args.slice(i + 1);
      break;
    } else if (a === "--uvx") {
      opts.transport = "stdio";
      opts.command = "uvx";
      opts.commandArgs = args.slice(i + 1);
      break;
    } else if (a === "--cmd") {
      opts.transport = "stdio";
      const parts = (args[i + 1] || "").split(/\s+/);
      opts.command = parts[0];
      opts.commandArgs = parts.slice(1);
      i += 2;
      continue;
    } else if (a === "--stdio") {
      opts.transport = "stdio";
      opts.command = args[i + 1];
      opts.commandArgs = args.slice(i + 2);
      break;
    } else if (a === "--sse") {
      opts.transport = "sse";
      opts.url = args[i + 1];
      i += 2;
      continue;
    } else if (a === "--auth") {
      opts.auth = args[i + 1];
      i += 2;
      continue;
    } else if (a === "--output") {
      opts.output = args[i + 1];
      i += 2;
      continue;
    }
    i++;
  }

  if (!opts.transport) {
    console.error("Usage: node mcp-client.js [--node|--npx|--python|--uvx|--cmd|--stdio|--sse] ... [--output tools.json]");
    process.exit(1);
  }

  return opts;
}

function inferOutputPath(opts) {
  if (opts.output) {
    return opts.output;
  }

  let baseName = "tools";
  const args = opts.commandArgs || [];
  for (let i = args.length - 1; i >= 0; i--) {
    const value = args[i];
    if (/\.(js|ts|py)$/i.test(value)) {
      const normalized = value.replace(/[\\/]+$/, "");
      const parts = normalized.split(/[\\/]+/).filter(Boolean);
      const serversIndex = parts.lastIndexOf("servers");
      if (serversIndex >= 0 && parts[serversIndex + 1]) {
        baseName = parts[serversIndex + 1];
      } else {
        const parentDir = path.basename(path.dirname(normalized));
        if (parentDir && parentDir !== "." && parentDir !== path.sep && parentDir !== "dist" && parentDir !== "build" && parentDir !== "src") {
          baseName = parentDir;
        } else {
          baseName = path.basename(normalized).replace(/\.(js|ts|py)$/i, "");
        }
      }
      break;
    }
  }

  return path.join(__dirname, "out", `${baseName}_tool_schema.json`);
}

class StdioTransport {
  constructor(command, args, env = {}) {
    this.pending = new Map();
    this.msgId = 0;
    this.proc = spawn(command, args, {
      env: { ...process.env, ...env },
      stdio: ["pipe", "pipe", "pipe"],
    });

    const rl = readline.createInterface({ input: this.proc.stdout });
    rl.on("line", line => {
      line = line.trim();
      if (!line) return;
      let msg;
      try { msg = JSON.parse(line); } catch { return; }
      if (msg.id != null && this.pending.has(msg.id)) {
        this.pending.get(msg.id)(msg);
        this.pending.delete(msg.id);
      }
    });
  }

  request(method, params) {
    const id = ++this.msgId;
    const msg = { jsonrpc: "2.0", id, method };
    if (params !== undefined) msg.params = params;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Timeout: ${method}`));
      }, 30000);
      this.pending.set(id, resp => {
        clearTimeout(timer);
        if (resp.error) reject(new Error(`RPC ${resp.error.code}: ${resp.error.message}`));
        else resolve(resp.result);
      });
      this.proc.stdin.write(JSON.stringify(msg) + "\n", err => {
        if (err) reject(err);
      });
    });
  }

  notify(method, params) {
    const msg = { jsonrpc: "2.0", method };
    if (params !== undefined) msg.params = params;
    this.proc.stdin.write(JSON.stringify(msg) + "\n");
  }

  close() {
    this.proc.stdin.end();
    this.proc.kill();
  }
}

class SSETransport {
  constructor(url, auth) {
    this.url = new URL(url);
    this.auth = auth;
    this.pending = new Map();
    this.msgId = 0;
    this.postUrl = null;
    this.sseReq = null;
    this.ready = this._connect();
  }

  _connect() {
    return new Promise((resolve, reject) => {
      const lib = this.url.protocol === "https:" ? https : http;
      const headers = { Accept: "text/event-stream" };
      if (this.auth) headers["Authorization"] = this.auth;

      this.sseReq = lib.request(
        {
          hostname: this.url.hostname,
          port: this.url.port || (this.url.protocol === "https:" ? 443 : 80),
          path: this.url.pathname + this.url.search,
          method: "GET",
          headers,
        },
        res => {
          if (res.statusCode !== 200) {
            return reject(new Error(`SSE HTTP ${res.statusCode}`));
          }
          let buf = "";
          let eventType = "message";
          res.on("data", chunk => {
            buf += chunk.toString();
            const parts = buf.split("\n");
            buf = parts.pop();
            for (const line of parts) {
              if (line.startsWith("event:")) {
                eventType = line.slice(6).trim();
              } else if (line.startsWith("data:")) {
                const data = line.slice(5).trim();
                if (eventType === "endpoint") {
                  this.postUrl = new URL(data, this.url.origin).toString();
                  resolve();
                } else {
                  let msg;
                  try { msg = JSON.parse(data); } catch { return; }
                  if (msg.id != null && this.pending.has(msg.id)) {
                    this.pending.get(msg.id)(msg);
                    this.pending.delete(msg.id);
                  }
                }
                eventType = "message";
              }
            }
          });
          res.on("error", reject);
        }
      );
      this.sseReq.on("error", reject);
      this.sseReq.end();
    });
  }

  async _post(msg) {
    await this.ready;
    const body = JSON.stringify(msg);
    const u = new URL(this.postUrl);
    const lib = u.protocol === "https:" ? https : http;
    const headers = { "Content-Type": "application/json", "Content-Length": Buffer.byteLength(body) };
    if (this.auth) headers["Authorization"] = this.auth;
    return new Promise((resolve, reject) => {
      const req = lib.request(
        {
          hostname: u.hostname,
          port: u.port || (u.protocol === "https:" ? 443 : 80),
          path: u.pathname + u.search,
          method: "POST",
          headers,
        },
        res => {
          res.resume();
          res.on("end", resolve);
        }
      );
      req.on("error", reject);
      req.write(body);
      req.end();
    });
  }

  request(method, params) {
    const id = ++this.msgId;
    const msg = { jsonrpc: "2.0", id, method };
    if (params !== undefined) msg.params = params;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => {
        this.pending.delete(id);
        reject(new Error(`Timeout: ${method}`));
      }, 30000);
      this.pending.set(id, resp => {
        clearTimeout(timer);
        if (resp.error) reject(new Error(`RPC ${resp.error.code}: ${resp.error.message}`));
        else resolve(resp.result);
      });
      this._post(msg).catch(reject);
    });
  }

  notify(method, params) {
    const msg = { jsonrpc: "2.0", method };
    if (params !== undefined) msg.params = params;
    this._post(msg).catch(() => {});
  }

  close() {
    this.sseReq?.destroy();
  }
}

class MCPClient {
  constructor(transport) {
    this.t = transport;
    this.tools = [];
    this.serverInfo = null;
  }

  async connect() {
    this.serverInfo = await this.t.request("initialize", {
      protocolVersion: "2024-11-05",
      capabilities: { roots: { listChanged: true } },
      clientInfo: { name: "tool-schema-exporter", version: "1.0.0" },
    });
    this.t.notify("notifications/initialized");
    const result = await this.t.request("tools/list");
    this.tools = result.tools || [];
    return this;
  }

  close() {
    this.t.close();
  }
}

function writeJson(outputPath, payload) {
  const fullPath = path.resolve(outputPath);
  fs.mkdirSync(path.dirname(fullPath), { recursive: true });
  fs.writeFileSync(fullPath, JSON.stringify(payload, null, 2) + "\n", "utf8");
  console.log(`Wrote tools to ${fullPath}`);
}

async function main() {
  const opts = parseArgs(process.argv);
  const outputPath = inferOutputPath(opts);

  const transport =
    opts.transport === "stdio"
      ? new StdioTransport(opts.command, opts.commandArgs)
      : new SSETransport(opts.url, opts.auth);

  let client;
  try {
    client = await new MCPClient(transport).connect();
    writeJson(outputPath, {
      serverInfo: client.serverInfo,
      tools: client.tools,
    });
  } catch (err) {
    console.error(err.message);
    process.exitCode = 1;
  } finally {
    transport.close();
  }
}

main();
