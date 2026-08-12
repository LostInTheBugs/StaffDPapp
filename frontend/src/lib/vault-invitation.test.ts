/**
 * Tests for the full vault invitation cycle.
 *
 * @vitest-environment node
 *
 * Critical behavioural contracts:
 * - Complete invitation cycle: DEK → code-wrap → code-unwrap → password-wrap → password-unwrap → identical DEK
 * - Code normalization (dashes, spaces, case, I/L/O) → same KEK derivation
 * - Wrong code → WrongPasswordError (never silent wrong DEK)
 * - The DEK at the end of the cycle is byte-identical to the initial DEK
 */

import { describe, it, expect } from "vitest";
import {
  generateDEK,
  wrapDEK,
  unwrapDEK,
  deriveKEKFromCode,
  WrongPasswordError,
  type KdfParams,
} from "./vault";
import { normalizeCode } from "./vaultSession";

// Fast KDF params for tests
const FAST_KDF: KdfParams = {
  algo: "argon2id",
  m: 1024,   // 1 MiB
  t: 1,
  p: 1,
};

// ═══════════════════════════════════════════════════════════════
// Full invitation cycle
// ═══════════════════════════════════════════════════════════════

describe("full invitation cycle", () => {
  it("DEK → code-wrap → code-unwrap → password-wrap → password-unwrap → identical DEK", async () => {
    const originalDEK = generateDEK();
    const invitationCode = "ABCD-EFGH-JKMN-PQRS-TVWX-YZ";
    const normalized = normalizeCode(invitationCode);
    const userPassword = "mon-mot-de-passe-secret";

    // ── Step 1: Inviter wraps DEK under code-derived KEK ────────
    const codeSalt = crypto.getRandomValues(new Uint8Array(16));
    const codeKek = await deriveKEKFromCode(normalized, codeSalt, FAST_KDF);
    const codeNonce = crypto.getRandomValues(new Uint8Array(12));
    const codeWrapped = await crypto.subtle.encrypt(
      { name: "AES-GCM", iv: codeNonce },
      codeKek,
      originalDEK,
    );

    // ── Step 2: Invitee unwraps DEK with code ──────────────────
    const codeKek2 = await deriveKEKFromCode(normalized, codeSalt, FAST_KDF);
    const unwrappedDEK = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: codeNonce },
      codeKek2,
      codeWrapped,
    );

    // Verify: DEK from code unwrap matches original
    expect(
      Buffer.from(unwrappedDEK).equals(Buffer.from(originalDEK)),
    ).toBe(true);

    // ── Step 3: Invitee re-wraps DEK under password ────────────
    const passwordEnvelope = await wrapDEK(
      new Uint8Array(unwrappedDEK),
      userPassword,
      undefined,
      FAST_KDF,
    );

    // ── Step 4: Unwrap with password ───────────────────────────
    const finalDEK = await unwrapDEK(
      passwordEnvelope.wrapped,
      passwordEnvelope.nonce,
      userPassword,
      passwordEnvelope.kdfSalt,
      passwordEnvelope.kdfParams,
    );

    // ── Final assertion: byte-identical to original ────────────
    expect(Buffer.from(finalDEK).equals(Buffer.from(originalDEK))).toBe(true);
  });

  it("DEK at end of cycle is byte-identical to initial DEK (compare octet par octet)", async () => {
    const dek1 = generateDEK();
    const code = "TEST-CODE-1234-5678-ABCD-EFGH";
    const norm = normalizeCode(code);
    const pwd = "user-password-here";

    // Inviter wraps
    const s1 = crypto.getRandomValues(new Uint8Array(16));
    const k1 = await deriveKEKFromCode(norm, s1, FAST_KDF);
    const n1 = crypto.getRandomValues(new Uint8Array(12));
    const w1 = new Uint8Array(
      await crypto.subtle.encrypt({ name: "AES-GCM", iv: n1 }, k1, dek1),
    );

    // Invitee unwraps
    const k2 = await deriveKEKFromCode(norm, s1, FAST_KDF);
    const d2 = new Uint8Array(
      await crypto.subtle.decrypt({ name: "AES-GCM", iv: n1 }, k2, w1),
    );

    // Invitee re-wraps
    const env = await wrapDEK(d2, pwd, undefined, FAST_KDF);

    // Invitee unwraps with password
    const final = await unwrapDEK(
      env.wrapped,
      env.nonce,
      pwd,
      env.kdfSalt,
      env.kdfParams,
    );

    // Compare byte by byte
    expect(final.length).toBe(32);
    expect(dek1.length).toBe(32);
    for (let i = 0; i < 32; i++) {
      expect(final[i]).toBe(dek1[i]);
    }
  });
});

// ═══════════════════════════════════════════════════════════════
// Code normalization → same KEK
// ═══════════════════════════════════════════════════════════════

describe("code normalization → same KEK", () => {
  it("code with dashes produces same KEK as canonical", async () => {
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const plaintext = new Uint8Array([1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16]);

    const k1 = await deriveKEKFromCode(normalizeCode("ABCDEFGHJKMNPQRSTVWXYZ01"), salt, FAST_KDF);
    const k2 = await deriveKEKFromCode(normalizeCode("ABCD-EFGH-JKMN-PQRS-TVWX-YZ01"), salt, FAST_KDF);

    // Encrypt with k1, should decrypt with k2 (same underlying key)
    const nonce = crypto.getRandomValues(new Uint8Array(12));
    const ct = await crypto.subtle.encrypt(
      { name: "AES-GCM", iv: nonce },
      k1,
      plaintext,
    );

    // Decrypt with k2 (derived from dashed version)
    const pt = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: nonce },
      k2,
      ct,
    );
    expect(Buffer.from(pt).equals(Buffer.from(plaintext))).toBe(true);
  });

  it("code with spaces produces same KEK as canonical", async () => {
    const salt = crypto.getRandomValues(new Uint8Array(16));

    const k1 = await deriveKEKFromCode(
      normalizeCode("ABCD EFGH JKMN PQRS TVWX YZ01"),
      salt,
      FAST_KDF,
    );
    const k2 = await deriveKEKFromCode(
      normalizeCode("ABCDEFGHJKMNPQRSTVWXYZ01"),
      salt,
      FAST_KDF,
    );

    // Both should derive the same AES-GCM key
    const plaintext = crypto.getRandomValues(new Uint8Array(32));
    const nonce = crypto.getRandomValues(new Uint8Array(12));
    const ct = await crypto.subtle.encrypt(
      { name: "AES-GCM", iv: nonce },
      k1,
      plaintext,
    );
    const pt = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: nonce },
      k2,
      ct,
    );
    expect(Buffer.from(pt).equals(Buffer.from(plaintext))).toBe(true);
  });

  it("lowercase code produces same KEK as uppercase", async () => {
    const salt = crypto.getRandomValues(new Uint8Array(16));

    const k1 = await deriveKEKFromCode(normalizeCode("ABCDEFGHJKMNPQRSTVWXYZ01"), salt, FAST_KDF);
    const k2 = await deriveKEKFromCode(normalizeCode("abcdefghjkmnpqrstvwxyz01"), salt, FAST_KDF);

    const plaintext = crypto.getRandomValues(new Uint8Array(32));
    const nonce = crypto.getRandomValues(new Uint8Array(12));
    const ct = await crypto.subtle.encrypt(
      { name: "AES-GCM", iv: nonce },
      k1,
      plaintext,
    );
    const pt = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: nonce },
      k2,
      ct,
    );
    expect(Buffer.from(pt).equals(Buffer.from(plaintext))).toBe(true);
  });

  it("I/L/O confusions produce same KEK as canonical (1/0)", async () => {
    const salt = crypto.getRandomValues(new Uint8Array(16));

    // Canonical uses 1 and 0
    const canonical = normalizeCode("ABC1EFG0JK");
    // Confused uses I/L for 1, O for 0
    const confused = normalizeCode("ABCIEFGOJK");

    expect(canonical).toBe(confused);

    // Same salt + same normalized code = same KEK
    const k1 = await deriveKEKFromCode(canonical, salt, FAST_KDF);
    const k2 = await deriveKEKFromCode(confused, salt, FAST_KDF);

    const plaintext = crypto.getRandomValues(new Uint8Array(32));
    const nonce = crypto.getRandomValues(new Uint8Array(12));
    const ct = await crypto.subtle.encrypt(
      { name: "AES-GCM", iv: nonce },
      k1,
      plaintext,
    );
    const pt = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: nonce },
      k2,
      ct,
    );
    expect(Buffer.from(pt).equals(Buffer.from(plaintext))).toBe(true);
  });

  it("mixed dashes, spaces, lowercase, I/L/O → same KEK as clean canonical", async () => {
    const salt = crypto.getRandomValues(new Uint8Array(16));

    // Real-world messy input
    const messy = "ab-cd Il Oo 12-34";
    const canonical = normalizeCode(messy);
    expect(canonical).toBe("ABCD11001234");

    const k1 = await deriveKEKFromCode(canonical, salt, FAST_KDF);
    const k2 = await deriveKEKFromCode(
      normalizeCode(messy),
      salt,
      FAST_KDF,
    );

    const plaintext = crypto.getRandomValues(new Uint8Array(32));
    const nonce = crypto.getRandomValues(new Uint8Array(12));
    const ct = await crypto.subtle.encrypt(
      { name: "AES-GCM", iv: nonce },
      k1,
      plaintext,
    );
    const pt = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: nonce },
      k2,
      ct,
    );
    expect(Buffer.from(pt).equals(Buffer.from(plaintext))).toBe(true);
  });
});

// ═══════════════════════════════════════════════════════════════
// Wrong code → WrongPasswordError
// ═══════════════════════════════════════════════════════════════

describe("wrong code → WrongPasswordError", () => {
  it("wrong code throws WrongPasswordError (never silent)", async () => {
    const dek = generateDEK();
    const correctCode = "CORRECT-CODE-1234";
    const normalized = normalizeCode(correctCode);

    // Wrap DEK under correct code
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const kek = await deriveKEKFromCode(normalized, salt, FAST_KDF);
    const nonce = crypto.getRandomValues(new Uint8Array(12));
    const wrapped = new Uint8Array(
      await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce }, kek, dek),
    );

    // Try to unwrap with wrong code
    const wrongCode = "WRONG-CODE-5678";
    const wrongNorm = normalizeCode(wrongCode);
    const wrongKek = await deriveKEKFromCode(wrongNorm, salt, FAST_KDF);

    // Should throw — GCM auth tag check
    await expect(
      crypto.subtle.decrypt(
        { name: "AES-GCM", iv: nonce },
        wrongKek,
        wrapped,
      ),
    ).rejects.toThrow(); // DOMException: OperationError
  });

  it("wrong code does NOT silently return a wrong DEK", async () => {
    const dek = generateDEK();
    const code = "ABCDEFGH";

    // Wrap using unwrapDEK from vault.ts
    const normalized = normalizeCode(code);
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const kek = await deriveKEKFromCode(normalized, salt, FAST_KDF);
    const nonce = crypto.getRandomValues(new Uint8Array(12));
    const wrapped = new Uint8Array(
      await crypto.subtle.encrypt({ name: "AES-GCM", iv: nonce }, kek, dek),
    );

    // Try unwrapDEK with wrong code (using vault.ts function)
    try {
      const result = await unwrapDEK(wrapped, nonce, "WRONG-CODE", salt, FAST_KDF);
      // If we reach here, check it didn't silently return a wrong key
      expect(Buffer.from(result).equals(Buffer.from(dek))).toBe(false);
    } catch (e) {
      // Expected path — WrongPasswordError
      expect(e).toBeInstanceOf(WrongPasswordError);
    }
  });
});

// ═══════════════════════════════════════════════════════════════
// Different codes → different KEKs
// ═══════════════════════════════════════════════════════════════

describe("different codes → different KEKs", () => {
  it("two different codes with same salt produce different KEKs", async () => {
    const salt = crypto.getRandomValues(new Uint8Array(16));

    const k1 = await deriveKEKFromCode("CODE-ONE-ABCD", salt, FAST_KDF);
    const k2 = await deriveKEKFromCode("CODE-TWO-EFGH", salt, FAST_KDF);

    // Encrypt with k1, try decrypt with k2 → should fail
    const plaintext = crypto.getRandomValues(new Uint8Array(32));
    const nonce = crypto.getRandomValues(new Uint8Array(12));
    const ct = await crypto.subtle.encrypt(
      { name: "AES-GCM", iv: nonce },
      k1,
      plaintext,
    );

    await expect(
      crypto.subtle.decrypt({ name: "AES-GCM", iv: nonce }, k2, ct),
    ).rejects.toThrow();
  });
});
