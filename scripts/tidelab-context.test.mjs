import assert from "node:assert/strict";
import { execFileSync, spawnSync } from "node:child_process";
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import test from "node:test";

const cli = fileURLToPath(new URL("./tidelab-context.mjs", import.meta.url));

test("repo-local context skill has complete routing metadata", () => {
  const skill = readFileSync(new URL("../.agents/skills/tidelab-context/SKILL.md", import.meta.url), "utf8");
  assert.match(skill, /^---\r?\nname: tidelab-context\r?\ndescription: .+\r?\n---\r?\n/u);
  assert.doesNotMatch(skill, /\bTODO\b|\[TODO\]/u);
});

function git(root, ...args) {
  execFileSync("git", ["-C", root, ...args], { stdio: "ignore" });
}

function run(root, ...args) {
  return spawnSync(process.execPath, [cli, ...args], { cwd: root, encoding: "utf8" });
}

test("context reads one committed head and keeps working edits separate", () => {
  const root = mkdtempSync(join(tmpdir(), "tidelab-context-"));
  try {
    git(root, "init", "--initial-branch=main");
    git(root, "config", "user.name", "Fixture");
    git(root, "config", "user.email", "fixture@example.invalid");
    mkdirSync(join(root, "docs", "evidence"), { recursive: true });
    writeFileSync(join(root, "AGENTS.md"), "# Rules\nNo live trading without approval.\n");
    writeFileSync(join(root, "HANDOFF.md"), "# Handoff\n\nUpdated 2026-09-21.\n");
    writeFileSync(join(root, "docs", "CONTEXT_MAP.md"), "# Context map\nRead the handoff.\n");
    writeFileSync(join(root, "docs", "ROADMAP.md"), "# Roadmap\nPaper first; live later.\nFull cost includes drawdown.\n");
    writeFileSync(join(root, "docs", "evidence", "probe.md"), `# Probe\nSynthetic only.\n${"word ".repeat(100)}target-evidence\n`);
    git(root, "add", ".");
    git(root, "commit", "-m", "fixture");

    writeFileSync(join(root, "docs", "ROADMAP.md"), "# Roadmap\nUncommitted secret: should not appear.\n");
    const current = run(root, "current", "--json");
    assert.equal(current.status, 0);
    const packet = JSON.parse(current.stdout);
    assert.equal(packet.branch, "main");
    assert.equal(packet.dirtyCount, 1);
    assert.equal(packet.handoff.marker, "Updated 2026-09-21.");

    const found = run(root, "decision", "paper first", "--json");
    assert.equal(found.status, 0);
    assert.deepEqual(JSON.parse(found.stdout).results.map((item) => [item.path, item.line]), [["docs/ROADMAP.md", 2]]);
    assert.equal(run(root, "decision", "full raw").status, 1);
    assert.equal(run(root, "decision", "Uncommitted").status, 1);
    assert.match(run(root, "map").stdout, /Read the handoff/);
    assert.equal(run(root, "evidence", "Synthetic").status, 0);
    assert.match(run(root, "evidence", "target-evidence").stdout, /target-evidence/);
    assert.equal(run(root, "impact", "live later").status, 0);
    assert.equal(run(root, "impact", "sk-123456789012345").status, 2);
    assert.equal(run(root, "impact", "C:\\private\\path").status, 2);
    assert.equal(run(root, "impact", "person@example.com").status, 2);
    assert.equal(run(root, "impact", "https://example.com").status, 2);
  } finally {
    rmSync(root, { recursive: true, force: true });
  }
});
