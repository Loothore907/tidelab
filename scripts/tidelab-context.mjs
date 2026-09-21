#!/usr/bin/env node

import { execFileSync } from "node:child_process";

const MAX_TREE_BYTES = 2 * 1024 * 1024;
const MAX_BLOB_BYTES = 1024 * 1024;
const MAX_RESULTS = 12;
const MAX_PER_FILE = 3;
const MODES = new Set(["current", "map", "search-docs", "decision", "evidence", "impact"]);
const TEXT_EXTENSIONS = /\.(?:md|py|mjs|js|json|toml|txt|ya?ml)$/iu;

function git(root, ...args) {
  return execFileSync("git", ["-C", root, ...args], {
    encoding: "utf8",
    maxBuffer: MAX_TREE_BYTES,
    stdio: ["ignore", "pipe", "pipe"],
  });
}

function optionalGit(root, ...args) {
  try { return git(root, ...args).trim(); } catch { return null; }
}

function rootFromCwd() {
  return git(process.cwd(), "rev-parse", "--show-toplevel").trim();
}

function headFiles(root, head) {
  const raw = git(root, "ls-tree", "-r", "-z", "--long", head);
  return raw.split("\0").filter(Boolean).flatMap((line) => {
    const match = line.match(/^(100644|100755) blob [0-9a-f]+\s+(\d+)\t(.+)$/u);
    return match ? [{ path: match[3].replaceAll("\\", "/"), size: Number(match[2]) }] : [];
  });
}

function blob(root, head, entry) {
  if (!entry || entry.size > MAX_BLOB_BYTES) return null;
  const raw = execFileSync("git", ["-C", root, "show", `${head}:${entry.path}`], {
    encoding: "buffer",
    maxBuffer: MAX_BLOB_BYTES,
    stdio: ["ignore", "pipe", "pipe"],
  });
  if (raw.includes(0)) return null;
  return raw.toString("utf8");
}

function validateQuery(raw) {
  const query = raw.trim();
  if (query.length < 2 || query.length > 120 || /[\u0000-\u001f\u007f]/u.test(query)) throw Error("invalid query");
  if (/^(?:[a-z]:[\\/]|[\\/]|~[\\/])/iu.test(query) || /(^|[\\/])\.\.([\\/]|$)/u.test(query) || /\b[a-z][a-z0-9+.-]*:\/\//iu.test(query)) throw Error("path or URL rejected");
  if (/\b(?:sk-[a-z0-9_-]{10,}|gh[pousr]_[a-z0-9]{10,}|AKIA[0-9A-Z]{16})\b/iu.test(query) || /\b(?:password|secret|token|api[_ -]?key)\s*[:=]\s*\S+/iu.test(query) || /\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b/iu.test(query) || /\b[a-z0-9+/]{64,}={0,2}\b/iu.test(query)) throw Error("credential-shaped query rejected");
  return query;
}

function redact(value) {
  return value
    .replace(/\bsk-[a-z0-9_-]{10,}\b/giu, "<REDACTED>")
    .replace(/\bgh[pousr]_[a-z0-9]{10,}\b/giu, "<REDACTED>")
    .replace(/\bAKIA[0-9A-Z]{16}\b/gu, "<REDACTED>")
    .replace(/\beyJ[a-z0-9_-]{15,}\.[a-z0-9_-]{10,}\.[a-z0-9_-]{10,}\b/giu, "<REDACTED>")
    .replace(/\b(?:[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,})\b/giu, "<REDACTED-EMAIL>")
    .replace(/\b(password|secret|token|api[_ -]?key)\s*[:=]\s*\S+/giu, "$1=<REDACTED>")
    .replace(/\b[a-z0-9+/]{64,}={0,2}\b/giu, "<REDACTED>");
}

function eligible(path, mode) {
  if (mode === "evidence") return path.startsWith("docs/evidence/") && path.endsWith(".md");
  if (mode === "decision") return ["README.md", "HANDOFF.md", "docs/PLAN.md", "docs/ROADMAP.md", "docs/ARCHITECTURE.md", "docs/STRATEGY_RESEARCH.md", "docs/OPEN_SOURCE_AND_PUBLICATION.md"].includes(path);
  if (mode === "search-docs") return ["AGENTS.md", "README.md", "HANDOFF.md"].includes(path) || (path.startsWith("docs/") || path.startsWith(".agents/skills/")) && path.endsWith(".md");
  return TEXT_EXTENSIONS.test(path) && !path.startsWith(".github/");
}

function excerpt(line, phrase, tokens) {
  const safe = redact(line);
  const lower = safe.toLowerCase();
  const match = lower.indexOf(phrase);
  const position = match >= 0 ? match : Math.max(0, lower.indexOf(tokens[0]));
  const start = Math.max(0, position - 120);
  const end = Math.min(safe.length, start + 400);
  return `${start ? "…" : ""}${safe.slice(start, end).trim()}${end < safe.length ? "…" : ""}`;
}

function search(root, head, entries, mode, query) {
  const results = [];
  const phrase = query.toLowerCase();
  const tokens = phrase.split(/[^a-z0-9_]+/u).filter(Boolean);
  for (const entry of entries) {
    if (!eligible(entry.path, mode)) continue;
    const content = blob(root, head, entry);
    if (content === null) continue;
    let count = 0;
    for (const [index, line] of content.split(/\r?\n/u).entries()) {
      const lower = line.toLowerCase();
      const words = lower.split(/[^a-z0-9_]+/u);
      if (!lower.includes(phrase) && !tokens.every((token) => words.includes(token))) continue;
      results.push({ path: redact(entry.path), line: index + 1, text: excerpt(line, phrase, tokens) });
      if (++count === MAX_PER_FILE || results.length === MAX_RESULTS) break;
    }
    if (results.length === MAX_RESULTS) break;
  }
  return results;
}

function current(root, head, entries) {
  const branch = optionalGit(root, "symbolic-ref", "--quiet", "--short", "HEAD") ?? "detached HEAD";
  const upstream = optionalGit(root, "rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{upstream}");
  const counts = upstream ? optionalGit(root, "rev-list", "--left-right", "--count", `HEAD...${upstream}`)?.split(/\s+/u).map(Number) : null;
  const dirtyCount = git(root, "status", "--porcelain=v1", "--untracked-files=all").split(/\r?\n/u).filter(Boolean).length;
  const handoff = blob(root, head, entries.find((entry) => entry.path === "HANDOFF.md"));
  const handoffLines = handoff?.split(/\r?\n/u) ?? [];
  const markerIndex = handoffLines.findIndex((line) => line.startsWith("Updated "));
  const handoffMarker = markerIndex < 0 ? "No dated handoff marker at HEAD" : handoffLines[markerIndex];
  return {
    advisory: "Committed HEAD orientation only; working edits, GitHub, provider replies, and runtime state require fresh checks.",
    branch: redact(branch), head, upstream: upstream ? redact(upstream) : null,
    ahead: counts?.[0] ?? null, behind: counts?.[1] ?? null, dirtyCount,
    handoff: { path: "HANDOFF.md", line: markerIndex < 0 ? null : markerIndex + 1, marker: redact(handoffMarker) },
    map: "docs/CONTEXT_MAP.md",
    authorities: ["AGENTS.md", "HANDOFF.md", "docs/ROADMAP.md"],
  };
}

function output(value, json) {
  if (json) { console.log(JSON.stringify(value, null, 2)); return; }
  console.log("TIDELAB CONTEXT — ADVISORY, NOT AUTHORITY");
  if (value.results) {
    console.log(`Source: tracked regular-file blobs at ${value.head}; working edits excluded`);
    console.log(`Mode: ${value.mode}; query: ${value.query}`);
    for (const result of value.results) console.log(`${result.path}:${result.line}: ${result.text}`);
  } else if (value.content) {
    console.log(`Source: ${value.path} at ${value.head}; working edits excluded`);
    console.log(value.content);
  } else {
    console.log(value.advisory);
    console.log(`Repository: ${value.branch} @ ${value.head}`);
    console.log(`Upstream: ${value.upstream ?? "none"}; ahead ${value.ahead ?? "?"}, behind ${value.behind ?? "?"}; dirty paths ${value.dirtyCount}`);
    console.log(`${value.handoff.path}:${value.handoff.line}: ${value.handoff.marker}`);
    console.log(`Map: ${value.map}; authority: ${value.authorities.join(", ")}`);
  }
}

function main() {
  const args = process.argv.slice(2);
  const json = args.includes("--json");
  const positional = args.filter((arg) => arg !== "--json");
  if (positional.length === 0 || positional[0] === "--help") {
    console.log("Usage: node scripts/tidelab-context.mjs <current|map|search-docs|decision|evidence|impact> [query] [--json]");
    return;
  }
  const [mode, ...parts] = positional;
  if (!MODES.has(mode) || (["current", "map"].includes(mode) ? parts.length !== 0 : parts.length === 0)) throw Error("invalid mode or arguments");
  const root = rootFromCwd();
  const head = git(root, "rev-parse", "HEAD").trim();
  const entries = headFiles(root, head);
  if (mode === "current") { output(current(root, head, entries), json); return; }
  if (mode === "map") {
    const path = "docs/CONTEXT_MAP.md";
    const content = blob(root, head, entries.find((entry) => entry.path === path));
    if (content === null) throw Error("context map unavailable at HEAD");
    output({ head, path, content: redact(content).slice(0, 8000) }, json);
    return;
  }
  const query = validateQuery(parts.join(" "));
  const results = search(root, head, entries, mode, query);
  output({ head, mode, query: redact(query), results }, json);
  if (results.length === 0) process.exitCode = 1;
}

try { main(); } catch { console.error("tidelab-context: unavailable or rejected input"); process.exitCode = 2; }
