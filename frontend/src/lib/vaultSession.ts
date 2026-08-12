/**
 * vaultSession.ts — Pure logic for vault session management.
 *
 * ZERO React dependency, ZERO DOM — testable entirely in Node.
 * Exported pure functions are consumed by the useVault context hook.
 */

import {
  clearSessionDEK,
  isVaultUnlocked,
} from "./vault";

// ── Lock timer ──────────────────────────────────────────────────

const AUTO_LOCK_MS = 30 * 60 * 1000; // 30 minutes

let _lastActivity: number = Date.now();

/** Activity heartbeat — call on any user interaction to reset the timer. */
export function recordActivity(): void {
  _lastActivity = Date.now();
}

/** Check whether the vault should auto-lock due to inactivity. */
export function shouldAutoLock(): boolean {
  return Date.now() - _lastActivity > AUTO_LOCK_MS;
}

/** Reset the activity timer (e.g. after successful unlock). */
export function resetActivityTimer(): void {
  _lastActivity = Date.now();
}

/** Expose for tests only — not for application code. */
export function _getLastActivityForTest(): number {
  return _lastActivity;
}
export function _setLastActivityForTest(ts: number): void {
  _lastActivity = ts;
}

// ── Session state (pure queries) ─────────────────────────────────

export type VaultStatus = "disabled" | "locked" | "unlocked";

/**
 * Compute the vault status from context (no React).
 *
 * vaultEnabled: whether the org has pv_vault_enabled=true
 * hasOwnKey: whether the current user has a vault_key row
 *
 * Returns "disabled" if vault not enabled, "locked" if enabled but DEK not in
 * memory, "unlocked" if DEK is loaded.
 */
export function computeStatus(
  vaultEnabled: boolean,
  hasOwnKey: boolean,
): VaultStatus {
  if (!vaultEnabled) return "disabled";
  if (!hasOwnKey) return "disabled"; // user not yet enrolled
  return isVaultUnlocked() ? "unlocked" : "locked";
}

/**
 * Combined lock check: should we lock the vault?
 * Returns true if vault is unlocked AND the inactivity timer has expired.
 */
export function shouldLock(vaultEnabled: boolean): boolean {
  if (!vaultEnabled) return false;
  if (!isVaultUnlocked()) return false; // already locked
  return shouldAutoLock();
}

// ── Code normalization ──────────────────────────────────────────

/**
 * Normalize a user-entered invitation code for key derivation.
 *
 * Same normalization as the server-side security.py / normalize_invitation_code:
 * - Strip grouping hyphens and spaces
 * - Correct Crockford confusions: I, L → 1; O → 0
 * - Uppercase
 */
export function normalizeCode(raw: string): string {
  return raw
    .replace(/[-\s]/g, "")             // strip dashes and spaces
    .replace(/[iIlL]/g, "1")           // I, L → 1
    .replace(/[oO]/g, "0")             // O → 0
    .toUpperCase();
}

/**
 * Group a normalized code for display: XXXX-XXXX-XXXX-...
 *
 * For a 26-char Crockford code, produces: "XXXX-XXXX-XXXX-XXXX-XXXX-XXXX-XX"
 */
export function groupCode(code: string): string {
  const groups: string[] = [];
  for (let i = 0; i < code.length; i += 4) {
    groups.push(code.slice(i, i + 4));
  }
  return groups.join("-");
}

// ── Lock / unlock actions (pure side-effect orchestrators) ─────

/** Lock the vault: clear DEK, unset activity. */
export function lockVault(): void {
  clearSessionDEK();
}

/** Attempt unlock: if the DEK is properly set, record activity. */
export function markUnlocked(): void {
  if (isVaultUnlocked()) {
    resetActivityTimer();
  }
}
