/**
 * Tests for vault.ts — section encryption/decryption and invitation cycle.
 *
 * @vitest-environment node
 */
import { describe, it, expect, afterEach } from "vitest";
import {
  generateDEK,
  encryptSection,
  decryptSection,
  clearSessionDEK,
} from "./vault";

afterEach(() => {
  clearSessionDEK();
});

// ═══════════════════════════════════════════════════════════════════
// Section encryption round-trips
// ═══════════════════════════════════════════════════════════════════

describe("encryptSection ⇄ decryptSection", () => {
  it("round-trip: encrypt then decrypt returns exact plaintext", async () => {
    const dek = generateDEK();
    const encoder = new TextEncoder();
    const decoder = new TextDecoder();
    const plaintext = encoder.encode("Section confidentielle — litige en cours");

    const { ciphertext, nonce } = await encryptSection(dek, plaintext);
    const decrypted = await decryptSection(dek, ciphertext, nonce);

    expect(decoder.decode(decrypted)).toBe("Section confidentielle — litige en cours");
  });

  it("ciphertext does not contain the plaintext", async () => {
    const dek = generateDEK();
    const encoder = new TextEncoder();
    const decoder = new TextDecoder();
    const plaintext = encoder.encode("SECRET-DATA-12345");

    const { ciphertext } = await encryptSection(dek, plaintext);

    // The ciphertext must be different from the plaintext
    expect(Buffer.from(ciphertext).equals(Buffer.from(plaintext))).toBe(false);

    // The ciphertext must not contain the plaintext bytes as a substring
    const ctStr = decoder.decode(ciphertext);
    expect(ctStr.includes("SECRET-DATA-12345")).toBe(false);
  });

  it("two encryptSection calls with same plaintext produce DIFFERENT nonces", async () => {
    const dek = generateDEK();
    const encoder = new TextEncoder();
    const plaintext = encoder.encode("same content");

    const e1 = await encryptSection(dek, plaintext);
    const e2 = await encryptSection(dek, plaintext);

    // Nonces MUST differ (random per call)
    expect(Buffer.from(e1.nonce).equals(Buffer.from(e2.nonce))).toBe(false);

    // Ciphertexts MUST differ (different nonce → different ciphertext)
    expect(Buffer.from(e1.ciphertext).equals(Buffer.from(e2.ciphertext))).toBe(false);

    // But both must decrypt to the same plaintext
    const decoder = new TextDecoder();
    const d1 = await decryptSection(dek, e1.ciphertext, e1.nonce);
    const d2 = await decryptSection(dek, e2.ciphertext, e2.nonce);
    expect(decoder.decode(d1)).toBe("same content");
    expect(decoder.decode(d2)).toBe("same content");
  });

  it("tampered ciphertext throws on decrypt", async () => {
    const dek = generateDEK();
    const encoder = new TextEncoder();
    const plaintext = encoder.encode("test");

    const { ciphertext, nonce } = await encryptSection(dek, plaintext);
    const corrupted = new Uint8Array(ciphertext);
    corrupted[0] ^= 0xFF;

    await expect(
      decryptSection(dek, corrupted, nonce),
    ).rejects.toThrow();
  });

  it("wrong DEK throws on decrypt", async () => {
    const dek1 = generateDEK();
    const dek2 = generateDEK();
    const encoder = new TextEncoder();
    const plaintext = encoder.encode("test");

    const { ciphertext, nonce } = await encryptSection(dek1, plaintext);

    await expect(
      decryptSection(dek2, ciphertext, nonce),
    ).rejects.toThrow();
  });
});

// ═══════════════════════════════════════════════════════════════════
// Invitation cycle: unwrap with code → re-wrap with password
// ═══════════════════════════════════════════════════════════════════

describe("invitation cycle", () => {
  it("complete cycle: DEK survives unwrap(code) → re-wrap(password)", async () => {
    const { wrapDEK, unwrapDEK } = await import("./vault");

    const dek = generateDEK();
    const invitationCode = "ABCDEFGHJK12345678MNPQRSTV"; // 26 chars Crockford
    const userPassword = "mon-mot-de-passe-secret";

    // Step 1: Inviter wraps DEK under invitation code
    const fastKdf = { algo: "argon2id" as const, m: 1024, t: 1, p: 1 };
    const inviteEnvelope = await wrapDEK(dek, invitationCode, undefined, fastKdf);

    // Step 2: Invitee unwraps DEK with invitation code
    const unwrapped = await unwrapDEK(
      inviteEnvelope.wrapped,
      inviteEnvelope.nonce,
      invitationCode,
      inviteEnvelope.kdfSalt,
      inviteEnvelope.kdfParams,
    );

    // Verify the DEK matches
    expect(Buffer.from(unwrapped).equals(Buffer.from(dek))).toBe(true);

    // Step 3: Invitee re-wraps DEK under their password
    const userEnvelope = await wrapDEK(
      new Uint8Array(unwrapped),
      userPassword,
      undefined,
      fastKdf,
    );

    // Step 4: Invitee can now unwrap with their password
    const finalDEK = await unwrapDEK(
      userEnvelope.wrapped,
      userEnvelope.nonce,
      userPassword,
      userEnvelope.kdfSalt,
      userEnvelope.kdfParams,
    );

    expect(Buffer.from(finalDEK).equals(Buffer.from(dek))).toBe(true);
  });

  it("wrong invitation code cannot unwrap the DEK", async () => {
    const { wrapDEK, unwrapDEK, WrongPasswordError } = await import("./vault");

    const dek = generateDEK();
    const fastKdf = { algo: "argon2id" as const, m: 1024, t: 1, p: 1 };

    const inviteEnvelope = await wrapDEK(dek, "CORRECT-CODE-ABCDEFGHJK", undefined, fastKdf);

    await expect(
      unwrapDEK(
        inviteEnvelope.wrapped,
        inviteEnvelope.nonce,
        "WRONG-CODE-ABCDEFGHJK",
        inviteEnvelope.kdfSalt,
        inviteEnvelope.kdfParams,
      ),
    ).rejects.toThrow(WrongPasswordError);
  });
});
