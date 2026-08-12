/**
 * Tests for vaultSession.ts — pure vault session management logic.
 *
 * @vitest-environment node
 *
 * Critical behavioural contracts:
 * - Auto-lock after 30 minutes of inactivity
 * - Activity resets the timer
 * - Code normalization: dashes, spaces, case, I/L → 1, O → 0
 * - Status computation: disabled / locked / unlocked
 * - lockVault clears DEK, markUnlocked resets timer
 */

import { describe, it, expect, beforeEach, afterEach } from "vitest";
import {
  recordActivity,
  shouldAutoLock,
  resetActivityTimer,
  computeStatus,
  shouldLock,
  normalizeCode,
  groupCode,
  lockVault,
  markUnlocked,
  _getLastActivityForTest,
  _setLastActivityForTest,
} from "./vaultSession";
import {
  setSessionDEK,
  clearSessionDEK,
  isVaultUnlocked,
  getSessionDEK,
} from "./vault";

beforeEach(() => {
  clearSessionDEK();
  resetActivityTimer();
});

afterEach(() => {
  clearSessionDEK();
});

// ═══════════════════════════════════════════════════════════════
// Auto-lock timer
// ═══════════════════════════════════════════════════════════════

describe("auto-lock timer", () => {
  it("shouldAutoLock returns false right after reset", () => {
    resetActivityTimer();
    expect(shouldAutoLock()).toBe(false);
  });

  it("shouldAutoLock returns true after > 30 minutes of inactivity", () => {
    _setLastActivityForTest(Date.now() - 31 * 60 * 1000);
    expect(shouldAutoLock()).toBe(true);
  });

  it("shouldAutoLock returns false at exactly 30 minutes (boundary)", () => {
    // At exactly 30 min: Date.now() - _lastActivity === AUTOLOCK_MS
    // shouldAutoLock uses > so the boundary should NOT lock
    _setLastActivityForTest(Date.now() - 30 * 60 * 1000);
    expect(shouldAutoLock()).toBe(false);
  });

  it("shouldAutoLock returns true at 30 min + 1 ms", () => {
    _setLastActivityForTest(Date.now() - 30 * 60 * 1000 - 1);
    expect(shouldAutoLock()).toBe(true);
  });

  it("recordActivity resets the timer", () => {
    _setLastActivityForTest(Date.now() - 40 * 60 * 1000); // 40 min ago
    expect(shouldAutoLock()).toBe(true);
    recordActivity();
    expect(shouldAutoLock()).toBe(false);
  });

  it("30 minutes of inactivity → locked; recent activity → unlocked", () => {
    // Test the full boolean decision
    // Inactive for 31 min
    _setLastActivityForTest(Date.now() - 31 * 60 * 1000);
    expect(shouldAutoLock()).toBe(true);

    // Recent activity
    recordActivity();
    expect(shouldAutoLock()).toBe(false);
  });
});

// ═══════════════════════════════════════════════════════════════
// Status computation
// ═══════════════════════════════════════════════════════════════

describe("computeStatus", () => {
  it("returns 'disabled' when vault not enabled", () => {
    expect(computeStatus(false, false)).toBe("disabled");
    expect(computeStatus(false, true)).toBe("disabled");
  });

  it("returns 'disabled' when vault enabled but user has no key", () => {
    expect(computeStatus(true, false)).toBe("disabled");
  });

  it("returns 'locked' when vault enabled, user has key, DEK not in memory", () => {
    clearSessionDEK();
    expect(computeStatus(true, true)).toBe("locked");
  });

  it("returns 'unlocked' when vault enabled, user has key, DEK in memory", () => {
    const dek = new Uint8Array(32).fill(0x42);
    setSessionDEK(dek);
    expect(computeStatus(true, true)).toBe("unlocked");
  });
});

// ═══════════════════════════════════════════════════════════════
// shouldLock — combined decision
// ═══════════════════════════════════════════════════════════════

describe("shouldLock", () => {
  it("returns false when vault not enabled", () => {
    expect(shouldLock(false)).toBe(false);
  });

  it("returns false when vault enabled but DEK not in memory", () => {
    clearSessionDEK();
    _setLastActivityForTest(Date.now() - 40 * 60 * 1000);
    expect(shouldLock(true)).toBe(false);
  });

  it("returns false when DEK in memory and activity is recent", () => {
    setSessionDEK(new Uint8Array(32));
    recordActivity();
    expect(shouldLock(true)).toBe(false);
  });

  it("returns true when DEK in memory and inactive > 30 min", () => {
    setSessionDEK(new Uint8Array(32));
    _setLastActivityForTest(Date.now() - 31 * 60 * 1000);
    expect(shouldLock(true)).toBe(true);
  });
});

// ═══════════════════════════════════════════════════════════════
// Code normalization
// ═══════════════════════════════════════════════════════════════

describe("normalizeCode", () => {
  it("removes hyphens", () => {
    expect(normalizeCode("ABCD-EFGH-JKMN")).toBe("ABCDEFGHJKMN");
  });

  it("removes spaces", () => {
    expect(normalizeCode("ABCD EFGH JKMN")).toBe("ABCDEFGHJKMN");
  });

  it("uppercases lowercase characters", () => {
    expect(normalizeCode("abcdefghjkmn")).toBe("ABCDEFGHJKMN");
  });

  it("corrects I → 1", () => {
    expect(normalizeCode("ABCDIEFGH")).toBe("ABCD1EFGH");
    expect(normalizeCode("abcdiefgh")).toBe("ABCD1EFGH");
  });

  it("corrects L → 1", () => {
    expect(normalizeCode("ABCDLEFGH")).toBe("ABCD1EFGH");
    expect(normalizeCode("abcdlefgh")).toBe("ABCD1EFGH");
  });

  it("corrects O → 0", () => {
    expect(normalizeCode("ABCDOEFGH")).toBe("ABCD0EFGH");
    expect(normalizeCode("abcdoefgh")).toBe("ABCD0EFGH");
  });

  it("handles mixed input with dashes, spaces, case, and confusions", () => {
    // Input: "ab-cd Il Oo" → should become "ABCD11100"
    expect(normalizeCode("ab-cd Il Oo")).toBe("ABCD1100");
  });

  it("produces the same output for visually ambiguous codes", () => {
    // Same underlying code, different human entry patterns
    const a = normalizeCode("ABCD-EFGH-JKMN-PQRS-TVWX-YZ");
    const b = normalizeCode("abcd efgh jkmn pqrs tvwx yz");
    const c = normalizeCode("ABCDEFGHJKMNPQRSTVWXYZ");
    expect(a).toBe(b);
    expect(b).toBe(c);
  });

  it("I/L/O confusion produces the same code as canonical", () => {
    // Canonical uses 1 and 0, human types I/L/O
    const canonical = normalizeCode("ABC1-EFG0-JKMN");
    const confused = normalizeCode("ABCI-EFGO-JKMN");
    expect(confused).toBe(canonical);
  });
});

// ═══════════════════════════════════════════════════════════════
// groupCode
// ═══════════════════════════════════════════════════════════════

describe("groupCode", () => {
  it("groups a 26-char code into XXXX-XXXX-...", () => {
    const code = "ABCDEFGHJKMNPQRSTVWXYZ01";
    const grouped = groupCode(code);
    expect(grouped).toBe("ABCD-EFGH-JKMN-PQRS-TVWX-YZ01");
  });

  it("groups shorter codes", () => {
    expect(groupCode("ABCDEFGH")).toBe("ABCD-EFGH");
  });

  it("groups codes not divisible by 4", () => {
    expect(groupCode("ABCDE")).toBe("ABCD-E");
  });
});

// ═══════════════════════════════════════════════════════════════
// lockVault / markUnlocked
// ═══════════════════════════════════════════════════════════════

describe("lockVault", () => {
  it("clears the DEK from memory", () => {
    setSessionDEK(new Uint8Array(32).fill(0xAA));
    expect(isVaultUnlocked()).toBe(true);
    lockVault();
    expect(isVaultUnlocked()).toBe(false);
    expect(getSessionDEK()).toBeNull();
  });

  it("is idempotent (calling lock on already-locked is safe)", () => {
    lockVault();
    lockVault();
    expect(isVaultUnlocked()).toBe(false);
  });
});

describe("markUnlocked", () => {
  it("resets activity timer when DEK is in memory", () => {
    setSessionDEK(new Uint8Array(32));
    _setLastActivityForTest(Date.now() - 40 * 60 * 1000);
    markUnlocked();
    expect(shouldAutoLock()).toBe(false);
  });

  it("does nothing if DEK is not in memory (no crash)", () => {
    clearSessionDEK();
    _setLastActivityForTest(Date.now() - 40 * 60 * 1000);
    markUnlocked(); // should not throw
    // Timer NOT reset since DEK wasn't present
    expect(shouldAutoLock()).toBe(true);
  });
});
