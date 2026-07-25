#!/usr/bin/env node
/**
 * Dependency audit gate: fails when `npm audit` reports high/critical
 * advisories in production dependencies, minus a reviewed allowlist.
 *
 * `npm audit` has no built-in ignore mechanism, so exemptions live here.
 * Every allowlist entry MUST state why the advisory does not apply and when
 * to re-check. Keep entries rare and specific.
 */
"use strict";

const { spawnSync } = require("node:child_process");

const ALLOWLIST = [
  {
    advisory: "GHSA-qwww-vcr4-c8h2", // react-router RSC-mode CSRF bypass
    package: "react-router",
    reason:
      "Affects only the unstable RSC / server-action code paths (patched in 8.3.0). " +
      "skill-manager is a client-only SPA: react-router-dom in library mode, no SSR, " +
      "no RSC, no framework mode. Re-check if the app adopts SSR/RSC or upgrades " +
      "react-router within the affected range.",
  },
];

const FAIL_SEVERITIES = new Set(["high", "critical"]);

function collectAdvisories(auditJson) {
  const findings = [];
  const vulnerabilities = auditJson.vulnerabilities ?? {};
  for (const [name, vuln] of Object.entries(vulnerabilities)) {
    const via = Array.isArray(vuln.via) ? vuln.via : [];
    const advisories = via.filter((entry) => entry && typeof entry === "object" && entry.url);
    if (advisories.length === 0) {
      findings.push({ name, severity: vuln.severity, id: null, title: String(vuln.via) });
      continue;
    }
    for (const advisory of advisories) {
      findings.push({ name, severity: advisory.severity ?? vuln.severity, id: extractAdvisoryId(advisory.url), title: advisory.title });
    }
  }
  return findings;
}

function extractAdvisoryId(url) {
  const match = /advisories\/(GHSA-[a-z0-9-]+)/i.exec(String(url ?? ""));
  return match ? match[1] : null;
}

function main() {
  const result = spawnSync("npm", ["audit", "--omit=dev", "--json"], { encoding: "utf-8" });
  let auditJson;
  try {
    auditJson = JSON.parse(result.stdout);
  } catch {
    process.stderr.write(`audit_gate: could not parse npm audit output.\n${result.stderr}\n${result.stdout}\n`);
    process.exit(2);
  }

  const findings = collectAdvisories(auditJson);
  const failures = [];
  for (const finding of findings) {
    if (!FAIL_SEVERITIES.has(finding.severity)) {
      process.stdout.write(`info: ${finding.severity} ${finding.name} (${finding.id ?? finding.title}) — below gate threshold\n`);
      continue;
    }
    const exemption = ALLOWLIST.find((entry) => entry.advisory === finding.id && entry.package === finding.name);
    if (exemption) {
      process.stdout.write(`allowlisted: ${finding.id} ${finding.name} — ${exemption.reason}\n`);
      continue;
    }
    failures.push(finding);
  }

  if (failures.length > 0) {
    process.stderr.write("\nDependency audit gate FAILED:\n");
    for (const failure of failures) {
      process.stderr.write(`  ${failure.severity}  ${failure.name}  ${failure.id ?? ""}  ${failure.title}\n`);
    }
    process.stderr.write("Fix the dependency, or add a justified allowlist entry in scripts/audit_gate.cjs.\n");
    process.exit(1);
  }
  process.stdout.write("Dependency audit gate passed.\n");
}

main();
