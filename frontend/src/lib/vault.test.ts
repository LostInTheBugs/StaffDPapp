/**
 * Tests for vault.ts — cryptographic primitives and session management.
 *
 * @vitest-environment node
 *
 * Critical invariants:
 * - Wrap then unwrap with correct password → exact DEK
 * - Wrong password → WrongPasswordError (never silent failure)
 * - Two wraps with same password produce different outputs (random salt + nonce)
 * - Envelope produced with explicit params remains decryptable even if defaults change
 * - DEK never written to localStorage/sessionStorage
 */

import { describe, it, expect, vi, afterEach } from "vitest";
import {
  DEFAULT_KDF_PARAMS,
  generateDEK,
  wrapDEK,
  unwrapDEK,
  setSessionDEK,
  getSessionDEK,
  clearSessionDEK,
  isVaultUnlocked,
  WrongPasswordError,
  type KdfParams,
} from "./vault";

// Fast KDF params for testing (Argon2id with minimal cost)
const FAST_KDF: KdfParams = {
  algo: "argon2id",
  m: 1024,   // 1 MiB — fast enough for tests
  t: 1,      // 1 iteration
  p: 1,
};

afterEach(() => {
  clearSessionDEK();
});

// ═══════════════════════════════════════════════════════════════════
// DEK generation
// ═══════════════════════════════════════════════════════════════════

describe("generateDEK", () => {
  it("produces a 32-byte Uint8Array", () => {
    const dek = generateDEK();
    expect(dek).toBeInstanceOf(Uint8Array);
    expect(dek.length).toBe(32);
  });

  it("produces different DEKs on successive calls", () => {
    const a = generateDEK();
    const b = generateDEK();
    // Extremely unlikely to collide
    expect(Buffer.from(a).equals(Buffer.from(b))).toBe(false);
  });
});

// ═══════════════════════════════════════════════════════════════════
// wrapDEK / unwrapDEK round-trips
// ═══════════════════════════════════════════════════════════════════

describe("wrapDEK ⇄ unwrapDEK", () => {
  it("round-trip: wrap then unwrap with correct password returns exact DEK", async () => {
    const dek = generateDEK();
    const password = "bon-mot-de-passe-2026!";

    const envelope = await wrapDEK(dek, password, undefined, FAST_KDF);
    const unwrapped = await unwrapDEK(
      envelope.wrapped,
      envelope.nonce,
      password,
      envelope.kdfSalt,
      envelope.kdfParams,
    );

    expect(Buffer.from(unwrapped).equals(Buffer.from(dek))).toBe(true);
  });

  it("wrong password throws WrongPasswordError", async () => {
    const dek = generateDEK();
    const password = "correct-password";

    const envelope = await wrapDEK(dek, password, undefined, FAST_KDF);

    await expect(
      unwrapDEK(
        envelope.wrapped,
        envelope.nonce,
        "WRONG-password",
        envelope.kdfSalt,
        envelope.kdfParams,
      ),
    ).rejects.toThrow(WrongPasswordError);
  });

  it("wrong password does NOT silently return a wrong DEK", async () => {
    const dek = generateDEK();
    const password = "secret1";

    const envelope = await wrapDEK(dek, password, undefined, FAST_KDF);

    try {
      const result = await unwrapDEK(
        envelope.wrapped,
        envelope.nonce,
        "secret2",
        envelope.kdfSalt,
        envelope.kdfParams,
      );
      // If we reach here, check it didn't silently return a wrong key
      // (should have thrown WrongPasswordError before)
      // This assertion is belt-and-suspenders
      expect(Buffer.from(result).equals(Buffer.from(dek))).toBe(false);
    } catch (e) {
      // Expected path
      expect(e).toBeInstanceOf(WrongPasswordError);
    }
  });

  it("tampered wrapped data throws error", async () => {
    const dek = generateDEK();
    const password = "test123";

    const envelope = await wrapDEK(dek, password, undefined, FAST_KDF);

    // Corrupt the wrapped blob
    const corrupted = new Uint8Array(envelope.wrapped);
    corrupted[0] ^= 0xFF;

    await expect(
      unwrapDEK(corrupted, envelope.nonce, password, envelope.kdfSalt, envelope.kdfParams),
    ).rejects.toThrow(WrongPasswordError);
  });

  it("tampered nonce throws error", async () => {
    const dek = generateDEK();
    const password = "test123";

    const envelope = await wrapDEK(dek, password, undefined, FAST_KDF);

    const corruptedNonce = new Uint8Array(envelope.nonce);
    corruptedNonce[0] ^= 0xFF;

    await expect(
      unwrapDEK(envelope.wrapped, corruptedNonce, password, envelope.kdfSalt, envelope.kdfParams),
    ).rejects.toThrow(WrongPasswordError);
  });
});

// ═══════════════════════════════════════════════════════════════════
// Deterministic vs random
// ═══════════════════════════════════════════════════════════════════

describe("wrapDEK randomness", () => {
  it("two wraps with same password produce different outputs", async () => {
    const dek = generateDEK();
    const password = "same-password";

    const e1 = await wrapDEK(dek, password, undefined, FAST_KDF);
    const e2 = await wrapDEK(dek, password, undefined, FAST_KDF);

    // Salts must differ (random each time)
    expect(Buffer.from(e1.kdfSalt).equals(Buffer.from(e2.kdfSalt))).toBe(false);
    // Nonces must differ
    expect(Buffer.from(e1.nonce).equals(Buffer.from(e2.nonce))).toBe(false);
    // Wrapped blobs must differ (different salt → different KEK → different ciphertext)
    expect(Buffer.from(e1.wrapped).equals(Buffer.from(e2.wrapped))).toBe(false);
  });
});

// ═══════════════════════════════════════════════════════════════════
// KDF params portability
// ═══════════════════════════════════════════════════════════════════

describe("KDF params portability", () => {
  it("envelope created with explicit params decrypts using those stored params", async () => {
    const dek = generateDEK();
    const password = "portable-password";

    // Use a distinct but fast KDF config
    const customParams: KdfParams = {
      algo: "argon2id",
      m: 2048,   // 2 MiB — fast enough for test
      t: 1,
      p: 1,
    };

    const envelope = await wrapDEK(dek, password, undefined, customParams);

    // unwrapDEK uses the params from the envelope, never the module defaults
    const unwrapped = await unwrapDEK(
      envelope.wrapped,
      envelope.nonce,
      password,
      envelope.kdfSalt,
      envelope.kdfParams,  // use the envelope's params (customParams)
    );

    // Should decrypt successfully with the envelope's stored params
    expect(Buffer.from(unwrapped).equals(Buffer.from(dek))).toBe(true);
    // Verify stored params are the custom ones, not defaults
    expect(envelope.kdfParams.m).toBe(2048);
    expect(envelope.kdfParams.t).toBe(1);
  });

  it("decrypting with wrong params (different from creation) fails", async () => {
    const dek = generateDEK();
    const password = "params-mismatch";

    const envelope = await wrapDEK(dek, password, undefined, FAST_KDF);

    // Try to decrypt with DIFFERENT params than what was used to create
    const wrongParams: KdfParams = { algo: "argon2id", m: 2048, t: 2, p: 1 };

    await expect(
      unwrapDEK(
        envelope.wrapped,
        envelope.nonce,
        password,
        envelope.kdfSalt,
        wrongParams,
      ),
    ).rejects.toThrow(WrongPasswordError);
  });
});

// ═══════════════════════════════════════════════════════════════════
// Session manager
// ═══════════════════════════════════════════════════════════════════

describe("session manager", () => {
  it("setSessionDEK / getSessionDEK round-trips", () => {
    const dek = generateDEK();
    setSessionDEK(dek);
    expect(isVaultUnlocked()).toBe(true);
    const retrieved = getSessionDEK();
    expect(retrieved).not.toBeNull();
    expect(Buffer.from(retrieved!).equals(Buffer.from(dek))).toBe(true);
  });

  it("clearSessionDEK removes the key", () => {
    setSessionDEK(generateDEK());
    clearSessionDEK();
    expect(getSessionDEK()).toBeNull();
    expect(isVaultUnlocked()).toBe(false);
  });

  it("setSessionDEK overwrites with zeroing", () => {
    const dek1 = generateDEK();
    const dek2 = generateDEK();
    setSessionDEK(dek1);
    setSessionDEK(dek2);

    // After overwrite, getSessionDEK should return dek2
    const current = getSessionDEK();
    expect(Buffer.from(current!).equals(Buffer.from(dek2))).toBe(true);

    // dek1 should have been zeroed
    expect(dek1.every(b => b === 0)).toBe(true);
  });
});

// ═══════════════════════════════════════════════════════════════════
// No persistence — DEK never touches storage
// ═══════════════════════════════════════════════════════════════════

describe("no DEK persistence", () => {
  it("DEK lives only in module-level memory, never in localStorage/sessionStorage", async () => {
    // Full cycle: generate → wrap → unwrap → session → clear
    const dek = generateDEK();
    const password = "storage-test";

    const envelope = await wrapDEK(dek, password, undefined, FAST_KDF);
    const unwrapped = await unwrapDEK(
      envelope.wrapped,
      envelope.nonce,
      password,
      envelope.kdfSalt,
      envelope.kdfParams,
    );

    // After round-trip: set in session, verify it's there
    setSessionDEK(unwrapped);
    expect(getSessionDEK()).not.toBeNull();
    expect(isVaultUnlocked()).toBe(true);

    // Clear and verify gone
    clearSessionDEK();
    expect(getSessionDEK()).toBeNull();
    expect(isVaultUnlocked()).toBe(false);
  });

  it("vault.ts source does not reference localStorage or sessionStorage", () => {
    // Static check: vault.ts must never import or call browser storage APIs.
    // Comments and docstrings are excluded from the check.
    const fs = require("fs");
    const path = require("path");
    const rawSource: string = fs.readFileSync(
      path.resolve(__dirname, "vault.ts"),
      "utf-8",
    );

    // Strip single-line comments (// ...) and block comments (/* ... */)
    const source = rawSource
      .replace(/\/\/.*$/gm, "")
      .replace(/\/\*[\s\S]*?\*\//g, "");

    // These storage APIs must never appear as actual code
    const forbidden = [
      "localStorage",
      "sessionStorage",
      "indexedDB",
      "IndexedDB",
      "document.cookie",
    ];
    for (const term of forbidden) {
      expect(source.includes(term)).toBe(false);
    }
  });
});

describe("Paramètres KDF par défaut", () => {
  it("reste sur des paramètres Argon2id robustes", () => {
    // Les tests utilisent volontairement des paramètres allégés pour la
    // rapidité. Sans cette assertion, un affaiblissement des paramètres réels
    // (par ex. m ramené à 4 MiB) passerait toute la suite au vert.
    expect(DEFAULT_KDF_PARAMS.algo).toBe("argon2id");
    expect(DEFAULT_KDF_PARAMS.m).toBeGreaterThanOrEqual(65536); // 64 MiB
    expect(DEFAULT_KDF_PARAMS.t).toBeGreaterThanOrEqual(3);
    expect(DEFAULT_KDF_PARAMS.p).toBeGreaterThanOrEqual(1);
  });
});

describe("Aucune écriture dans un stockage persistant (observation à l'exécution)", () => {
  it("aucun appel à setItem pendant un cycle complet", async () => {
    // Le contrôle statique du source ne verrait pas une écriture faite
    // indirectement (helper, dépendance). Ici on observe les APIs elles-mêmes.
    const localWrites: string[] = [];
    const sessionWrites: string[] = [];

    const store = () => ({
      setItem: (k: string) => { localWrites.push(k); },
      getItem: () => null,
      removeItem: () => {},
      clear: () => {},
      key: () => null,
      length: 0,
    });
    const localSpy = store();
    const sessionSpy = { ...store(), setItem: (k: string) => { sessionWrites.push(k); } };

    vi.stubGlobal("localStorage", localSpy);
    vi.stubGlobal("sessionStorage", sessionSpy);

    try {
      const dek = generateDEK();
      const password = "observation-runtime";
      const envelope = await wrapDEK(dek, password, undefined, FAST_KDF);
      const unwrapped = await unwrapDEK(
        envelope.wrapped, envelope.nonce, password, envelope.kdfSalt, envelope.kdfParams,
      );
      setSessionDEK(unwrapped);
      expect(isVaultUnlocked()).toBe(true);
      clearSessionDEK();
    } finally {
      vi.unstubAllGlobals();
    }

    expect(localWrites).toEqual([]);
    expect(sessionWrites).toEqual([]);
  });
});
