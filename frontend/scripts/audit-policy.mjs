import { spawnSync } from "node:child_process";

const temporaryWaiver = {
  advisorySource: 1124282,
  advisoryUrl: "https://github.com/advisories/GHSA-qwww-vcr4-c8h2",
  packages: new Set(["react-router", "react-router-dom"]),
  expiresAt: new Date("2026-09-30T23:59:59Z"),
};

const npmCli = process.env.npm_execpath;
const audit = npmCli
  ? spawnSync(process.execPath, [npmCli, "audit", "--json"], {
      encoding: "utf8",
    })
  : spawnSync("npm", ["audit", "--json"], {
  encoding: "utf8",
});

if (audit.error) {
  console.error(`Unable to run npm audit: ${audit.error.message}`);
  process.exit(1);
}

let report;
try {
  report = JSON.parse(audit.stdout);
} catch {
  console.error("npm audit did not return valid JSON.");
  if (audit.stderr) {
    console.error(audit.stderr.trim());
  }
  process.exit(1);
}

if (report.error) {
  console.error(`npm audit failed: ${report.error.summary ?? report.error.message ?? "unknown error"}`);
  process.exit(1);
}

if (
  report.auditReportVersion !== 2 ||
  typeof report.vulnerabilities !== "object" ||
  report.vulnerabilities === null ||
  Array.isArray(report.vulnerabilities) ||
  typeof report.metadata?.vulnerabilities !== "object" ||
  report.metadata.vulnerabilities === null
) {
  console.error("Unsupported or incomplete npm audit report; failing closed.");
  process.exit(1);
}

const vulnerabilities = report.vulnerabilities;
const reportedCounts = report.metadata.vulnerabilities;
for (const severity of ["high", "critical", "total"]) {
  if (
    !Number.isInteger(reportedCounts[severity]) ||
    reportedCounts[severity] < 0
  ) {
    console.error(`npm audit report has an invalid ${severity} vulnerability count.`);
    process.exit(1);
  }
}

const observedHighOrCriticalCount = Object.values(vulnerabilities).filter(
  (vulnerability) =>
    vulnerability &&
    typeof vulnerability === "object" &&
    ["high", "critical"].includes(vulnerability.severity),
).length;
if (
  observedHighOrCriticalCount !==
  reportedCounts.high + reportedCounts.critical
) {
  console.error(
    "npm audit report counts do not match its vulnerability records; failing closed.",
  );
  process.exit(1);
}

function advisoryDetails(packageName, seen = new Set()) {
  if (seen.has(packageName)) {
    return [];
  }
  seen.add(packageName);

  const vulnerability = vulnerabilities[packageName];
  if (!vulnerability) {
    return [];
  }

  return (vulnerability.via ?? []).flatMap((entry) => {
    if (typeof entry === "string") {
      return advisoryDetails(entry, seen);
    }
    return [entry];
  });
}

const unexpected = [];
const waived = [];
const waiverExpired = Date.now() > temporaryWaiver.expiresAt.getTime();

for (const [packageName, vulnerability] of Object.entries(vulnerabilities)) {
  if (!["high", "critical"].includes(vulnerability.severity)) {
    continue;
  }

  const advisories = advisoryDetails(packageName);
  const isExactWaiver =
    !waiverExpired &&
    temporaryWaiver.packages.has(packageName) &&
    advisories.length > 0 &&
    advisories.every(
      (advisory) =>
        advisory.source === temporaryWaiver.advisorySource &&
        advisory.url === temporaryWaiver.advisoryUrl &&
        advisory.severity === "high",
    );

  if (isExactWaiver) {
    waived.push(packageName);
  } else {
    unexpected.push({
      packageName,
      severity: vulnerability.severity,
      advisories,
    });
  }
}

if (waiverExpired && waived.length === 0) {
  const stillAffected = [...temporaryWaiver.packages].some(
    (packageName) => vulnerabilities[packageName]?.severity === "high",
  );
  if (stillAffected) {
    unexpected.push({
      packageName: "react-router waiver",
      severity: "high",
      advisories: [{ title: `Temporary waiver expired on ${temporaryWaiver.expiresAt.toISOString()}` }],
    });
  }
}

if (unexpected.length > 0) {
  console.error("npm audit found an unapproved high/critical vulnerability:");
  for (const item of unexpected) {
    const titles = item.advisories.map((advisory) => advisory.title ?? advisory.url).filter(Boolean);
    console.error(`- ${item.packageName} (${item.severity}): ${titles.join("; ") || "unknown advisory"}`);
  }
  process.exit(1);
}

if (waived.length > 0) {
  console.warn(
    `Temporarily waived ${temporaryWaiver.advisoryUrl} for ${waived.join(
      ", ",
    )}. This browser-only SPA does not use React Router RSC APIs. Review by ${temporaryWaiver.expiresAt
      .toISOString()
      .slice(0, 10)}.`,
  );
}

console.log("npm audit policy passed: no unapproved high/critical vulnerabilities.");
