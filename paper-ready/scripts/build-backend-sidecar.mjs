import { existsSync, mkdirSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import { spawnSync } from "node:child_process";

const root = join(dirname(fileURLToPath(import.meta.url)), "..");
const backendDir = join(root, "backend");
const binaryDir = join(root, "src-tauri", "binaries");
const entry = join(backendDir, "paper_ready_backend", "sidecar.py");

mkdirSync(binaryDir, { recursive: true });

const pythonCandidates = [
  process.env.PAPERREADY_PYTHON ? [process.env.PAPERREADY_PYTHON] : null,
  ["python"],
  ["conda", "run", "-n", "generic", "python"],
].filter(Boolean);

function findPythonWithPyInstaller() {
  for (const command of pythonCandidates) {
    const [bin, ...prefixArgs] = command;
    const result = spawnSync(bin, [...prefixArgs, "-m", "PyInstaller", "--version"], {
      cwd: root,
      encoding: "utf8",
    });
    if (result.status === 0) {
      return command;
    }
  }
  return null;
}

const python = findPythonWithPyInstaller();

if (!python) {
  console.warn("PyInstaller is not installed; skipping backend sidecar build.");
  process.exit(0);
}

const [pythonBin, ...pythonPrefixArgs] = python;

const result = spawnSync(
  pythonBin,
  [
    ...pythonPrefixArgs,
    "-m",
    "PyInstaller",
    "--onefile",
    "--name",
    "paperready-backend",
    "--distpath",
    binaryDir,
    "--workpath",
    join(root, "build", "pyinstaller"),
    "--specpath",
    join(root, "build", "pyinstaller"),
    entry,
  ],
  { cwd: backendDir, stdio: "inherit" },
);

if (result.status !== 0) {
  process.exit(result.status ?? 1);
}

if (!existsSync(join(binaryDir, "paperready-backend"))) {
  console.warn("Backend sidecar build completed, but binary was not found.");
}
