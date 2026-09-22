/** Scripted support-triage command agent using the official TypeSafe JavaScript SDK. */

import { createHash } from "node:crypto";
import { once } from "node:events";
import { readFile } from "node:fs/promises";
import { spawn } from "node:child_process";
import { createInterface } from "node:readline";
import { pathToFileURL } from "node:url";

import { TypeSafeClient, TypeSafeError, choice, noul, score } from "@typesafe-ai/sdk";

const QUESTIONS = {
  department: choice("Which team should handle this ticket?", {
    billing: "Payments, invoicing, and refunds",
    technical: "Bugs, outages, and integrations",
    sales: "Pricing, plans, and account questions",
  }),
  refund_requested: noul("The customer explicitly asks for a refund"),
  policy_supports: noul("The refund policy covers this situation", {
    true: "Duplicate charges are refundable",
    false: "Not covered",
  }),
  frustration: score("How frustrated is the customer?", [
    "Calm",
    "Frustrated but civil",
    "Very angry",
  ]),
};

class McpRpcError extends Error {}

function object(value, label) {
  if (value === null || Array.isArray(value) || typeof value !== "object") {
    throw new TypeError(`${label} must be a JSON object`);
  }
  return value;
}

function number(value, label) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new TypeError(`${label} must be a number`);
  }
  return value;
}

/** Minimal MT19937 implementation matching `random.Random(str).randrange()` in agent.py. */
class PythonRandom {
  constructor(seed) {
    const bytes = Buffer.from(seed, "utf8");
    const digest = createHash("sha512").update(bytes).digest();
    let value = BigInt(`0x${Buffer.concat([bytes, digest]).toString("hex")}`);
    const key = [];
    while (value > 0n) {
      key.push(Number(value & 0xffffffffn));
      value >>= 32n;
    }
    this.mt = new Uint32Array(624);
    this.index = 624;
    this.#initByArray(key);
  }

  #init(seed) {
    this.mt[0] = seed >>> 0;
    for (let index = 1; index < 624; index += 1) {
      const previous = this.mt[index - 1];
      this.mt[index] = (Math.imul(1812433253, previous ^ (previous >>> 30)) + index) >>> 0;
    }
  }

  #initByArray(key) {
    this.#init(19650218);
    let i = 1;
    let j = 0;
    for (let count = Math.max(624, key.length); count > 0; count -= 1) {
      const previous = this.mt[i - 1];
      this.mt[i] =
        ((this.mt[i] ^ Math.imul(previous ^ (previous >>> 30), 1664525)) + key[j] + j) >>> 0;
      i += 1;
      j += 1;
      if (i >= 624) {
        this.mt[0] = this.mt[623];
        i = 1;
      }
      if (j >= key.length) j = 0;
    }
    for (let count = 623; count > 0; count -= 1) {
      const previous = this.mt[i - 1];
      this.mt[i] =
        ((this.mt[i] ^ Math.imul(previous ^ (previous >>> 30), 1566083941)) - i) >>> 0;
      i += 1;
      if (i >= 624) {
        this.mt[0] = this.mt[623];
        i = 1;
      }
    }
    this.mt[0] = 0x80000000;
  }

  #uint32() {
    if (this.index >= 624) {
      for (let index = 0; index < 624; index += 1) {
        const value = (this.mt[index] & 0x80000000) | (this.mt[(index + 1) % 624] & 0x7fffffff);
        this.mt[index] =
          this.mt[(index + 397) % 624] ^
          (value >>> 1) ^
          (value & 1 ? 0x9908b0df : 0);
      }
      this.index = 0;
    }
    let value = this.mt[this.index];
    this.index += 1;
    value ^= value >>> 11;
    value ^= (value << 7) & 0x9d2c5680;
    value ^= (value << 15) & 0xefc60000;
    value ^= value >>> 18;
    return value >>> 0;
  }

  randrange(stop) {
    const bits = Math.floor(Math.log2(stop)) + 1;
    let value;
    do {
      value = this.#uint32() >>> (32 - bits);
    } while (value >= stop);
    return value;
  }
}

export function ticketIndexForSeed(seed, count) {
  return new PythonRandom(`${seed}:triage-ticket`).randrange(count);
}

function selectedTicket(task, seed) {
  const tickets = task.tickets;
  if (!Array.isArray(tickets) || tickets.length === 0) {
    throw new TypeError("task.tickets must be a non-empty list");
  }
  return object(tickets[ticketIndexForSeed(seed, tickets.length)], "selected ticket");
}

class McpSession {
  static async open(configPath) {
    const config = object(JSON.parse(await readFile(configPath, "utf8")), "MCP config");
    const servers = object(config.mcpServers, "mcpServers");
    const entries = Object.values(servers);
    if (entries.length !== 1) throw new Error("MCP config must contain exactly one server");
    const entry = object(entries[0], "MCP server entry");
    if (typeof entry.command !== "string") {
      throw new TypeError("MCP server command must be a string");
    }
    const args = entry.args ?? [];
    const extraEnv = object(entry.env ?? {}, "MCP server env");
    if (!Array.isArray(args) || args.some((item) => typeof item !== "string")) {
      throw new TypeError("MCP server args must be strings");
    }
    if (Object.values(extraEnv).some((value) => typeof value !== "string")) {
      throw new TypeError("MCP server env values must be strings");
    }
    const child = spawn(entry.command, args, {
      env: { ...process.env, ...extraEnv },
      stdio: ["pipe", "pipe", "ignore"],
    });
    const session = new McpSession(child);
    try {
      await session.rpc("initialize", {
        protocolVersion: "2026-07-28",
        capabilities: {},
        clientInfo: { name: "arci-jev-triage-node", version: "0.6" },
      });
      await session.send({ jsonrpc: "2.0", method: "notifications/initialized" });
      await session.rpc("tools/list", {});
      return session;
    } catch (error) {
      await session.close();
      throw error;
    }
  }

  constructor(child) {
    this.child = child;
    this.exited = once(child, "exit");
    this.lines = createInterface({ input: child.stdout, crlfDelay: Infinity })[Symbol.asyncIterator]();
    this.nextId = 0;
  }

  async send(message) {
    const line = `${JSON.stringify(message)}\n`;
    if (!this.child.stdin.write(line, "utf8")) await once(this.child.stdin, "drain");
  }

  async rpc(method, params) {
    this.nextId += 1;
    const id = `req-${this.nextId}`;
    await this.send({ jsonrpc: "2.0", id, method, params });
    while (true) {
      const line = await this.lines.next();
      if (line.done) throw new Error("MCP server exited before replying");
      const reply = object(JSON.parse(line.value), "MCP reply");
      if (reply.id !== id) continue;
      if ("error" in reply) throw new McpRpcError("MCP request failed");
      return object(reply.result, "MCP result");
    }
  }

  async call(name, args) {
    const result = await this.rpc("tools/call", { name, arguments: args });
    if (result.isError === true) throw new McpRpcError(`tool ${name} failed`);
  }

  async close() {
    if (!this.child.stdin.destroyed) this.child.stdin.end();
    const timer = setTimeout(() => this.child.kill("SIGKILL"), 5000);
    try {
      await this.exited;
    } finally {
      clearTimeout(timer);
    }
  }
}

function decideAction(answers) {
  const department = object(answers.department, "department answer");
  if (department.choice === "billing") {
    const refund = object(answers.refund_requested, "refund_requested answer");
    const policy = object(answers.policy_supports, "policy_supports answer");
    if (
      number(refund.noul, "refund_requested.noul") > 0.5 &&
      number(policy.noul, "policy_supports.noul") > 0.5
    ) {
      return "issue_refund";
    }
  }
  return "reply";
}

export function gatedAction(answers) {
  const department = object(answers.department, "department answer");
  const confidence = number(department.confidence, "department.confidence");
  if (confidence < 0.6) return null;
  const action = decideAction(answers);
  if (action === "issue_refund") {
    const refund = object(answers.refund_requested, "refund_requested answer");
    const policy = object(answers.policy_supports, "policy_supports answer");
    if (
      confidence < 0.85 ||
      Math.min(
        number(refund.noul, "refund_requested.noul"),
        number(policy.noul, "policy_supports.noul"),
      ) < 0.85
    ) {
      return null;
    }
  }
  return action;
}

async function act(configPath, ticket, action) {
  if (typeof ticket.ticket_id !== "string") throw new TypeError("ticket_id must be a string");
  const session = await McpSession.open(configPath);
  try {
    if (action === "issue_refund") {
      await session.call("issue_refund", { ticket_id: ticket.ticket_id });
    } else if (action === "escalate") {
      await session.call("escalate", {
        ticket_id: ticket.ticket_id,
        reason: "decision confidence or provider failure",
      });
    } else {
      await session.call("reply", {
        ticket_id: ticket.ticket_id,
        message: "Your ticket was routed to the right team.",
      });
    }
  } finally {
    await session.close();
  }
}

function parseArgs(argv) {
  const values = {};
  for (let index = 0; index < argv.length; index += 2) {
    const flag = argv[index];
    const value = argv[index + 1];
    if (!["--mcp-config", "--task-file", "--variant"].includes(flag) || value === undefined) {
      throw new Error("usage: agent.mjs --mcp-config PATH --task-file PATH --variant a|b|c");
    }
    values[flag] = value;
  }
  if (!values["--mcp-config"] || !values["--task-file"] || !["a", "b", "c"].includes(values["--variant"])) {
    throw new Error("usage: agent.mjs --mcp-config PATH --task-file PATH --variant a|b|c");
  }
  return values;
}

export async function main() {
  const args = parseArgs(process.argv.slice(2));
  const task = object(JSON.parse(await readFile(args["--task-file"], "utf8")), "task");
  const seed = Number.parseInt(process.env.ARCI_SEED ?? "", 10);
  if (!Number.isSafeInteger(seed)) throw new TypeError("ARCI_SEED must be an integer");
  const ticket = selectedTicket(task, seed);
  let action;
  try {
    const client = new TypeSafeClient();
    const response = await client.systemOne({
      state: { ticket },
      questions: QUESTIONS,
      model: "jev-latest",
    });
    action = gatedAction(response.answers);
  } catch (error) {
    if (!(error instanceof TypeSafeError)) throw error;
    action = null;
  }
  if (action === null) {
    if (args["--variant"] === "b") return;
    action = "escalate";
  }
  await act(args["--mcp-config"], ticket, action);
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  main().catch((error) => {
    console.error(error instanceof Error ? `${error.name}: ${error.message}` : "agent failed");
    process.exitCode = 1;
  });
}
