import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import os from "node:os";
import path from "node:path";

/**
 * A free-text value (operator prompt, classifier/follow-up message, …) staged
 * on disk as UTF-8 so a spawned Python CLI reads it as bytes from a file
 * instead of receiving it as a process argument.
 */
export type TextArgFile = {
  /** Absolute path to the UTF-8 temp file. Pass this as the CLI flag value. */
  path: string;
  /**
   * Best-effort removal of the backing temp dir. Idempotent; call once the
   * spawned child has closed (success, failure or timeout) so the operator's
   * text never lingers on disk longer than the single CLI invocation.
   */
  cleanup: () => void;
};

/**
 * Stage ``text`` in a fresh temp directory as a UTF-8 file and return its path
 * plus a cleanup callback.
 *
 * Why this exists (B204): the operator prompt and other free text used to be
 * passed as a process ARGV argument to the Python CLIs
 * (``spawn(python, [..., "--", trimmed])``). On some Windows consoles a
 * non-ASCII LEADING character in argv is mangled on the Node→OS→Python hop —
 * the operator saw "Ändra …" stored as "*ndra …". Bytes written to a UTF-8
 * file and read back with ``encoding="utf-8"`` round-trip every Swedish
 * character (å/ä/ö/Å/Ä/Ö, including the leading one) intact. This mirrors the
 * discovery-payload tempfile the prompt helper already used, generalised so
 * every prompt-bearing spawn seam can share one transport.
 *
 * The caller owns the lifecycle: push ``--<flag> <result.path>`` onto the
 * spawn args, then invoke ``result.cleanup()`` once the child has closed.
 */
export function writeTextArgFile(text: string, prefix = "sb-arg-"): TextArgFile {
  const dir = mkdtempSync(path.join(os.tmpdir(), prefix));
  const file = path.join(dir, "value.txt");
  writeFileSync(file, text, { encoding: "utf-8" });
  return {
    path: file,
    cleanup: () => {
      try {
        rmSync(dir, { recursive: true, force: true });
      } catch {
        // best-effort — the OS tmp reaper clears it on reboot if we miss.
      }
    },
  };
}
