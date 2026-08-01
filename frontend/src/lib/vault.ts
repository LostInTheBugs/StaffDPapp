/**
 * vault.ts — Cryptographic primitives for the PV vault (coffre-fort).
 *
 * All crypto happens in the browser via WebCrypto + hash-wasm (Argon2id).
 * The server NEVER sees a password, KEK, or DEK in clear.
 *
 * Architecture:
 *   DEK (Data Encryption Key) → 256-bit random, one per organization
 *   KEK (Key Encryption Key)  → derived from user password via Argon2id
 *   wrapped DEK                → AES-256-GCM(KEK, DEK), stored on server
 *
 * Session manager:
 *   The DEK lives only in module-level memory. Closing the tab = DEK lost.
 *   NEVER write to localStorage, sessionStorage, IndexedDB, or cookies.
 */

import { argon2id } from "hash-wasm";

// ── Types ──────────────────────────────────────────────────────────

export interface KdfParams {
  algo: "argon2id";
  m: number; // memorySize in KiB
  t: number; // iterations
  p: number; // parallelism
}

export interface WrappedKey {
  wrapped: Uint8Array; // AES-GCM(KEK, DEK) — 32 + 16 bytes
  nonce: Uint8Array; // 12 bytes
  kdfSalt: Uint8Array; // 16 bytes
  kdfParams: KdfParams;
  dekVersion: number;
}

export interface EncryptedSection {
  ciphertext: Uint8Array;
  nonce: Uint8Array; // 12 bytes, random per section
}

export const DEFAULT_KDF_PARAMS: KdfParams = {
  algo: "argon2id",
  m: 65536, // 64 MiB
  t: 3,
  p: 1,
};

async function deriveKEK(
  password: string,
  salt: Uint8Array,
  params: KdfParams,
): Promise<CryptoKey> {
  const raw = await argon2id({
    password,
    salt,
    iterations: params.t,
    parallelism: params.p,
    memorySize: params.m,
    hashLength: 32,
    outputType: "binary",
  });

  return crypto.subtle.importKey(
    "raw",
    raw,
    { name: "AES-GCM" },
    false,
    ["encrypt", "decrypt"],
  );
}

/** Import a raw 32-byte DEK as a WebCrypto AES-GCM key for section encryption. */
async function importDEK(dek: Uint8Array): Promise<CryptoKey> {
  return crypto.subtle.importKey(
    "raw",
    dek,
    { name: "AES-GCM" },
    false,
    ["encrypt", "decrypt"],
  );
}

// ── Public API ─────────────────────────────────────────────────────

/**
 * Generate a 256-bit Data Encryption Key from a CSPRNG.
 * NEVER persists — caller must keep it in memory or wrap it immediately.
 */
export function generateDEK(): Uint8Array {
  return crypto.getRandomValues(new Uint8Array(32));
}

/**
 * Wrap a DEK under a password-derived KEK (Argon2id + AES-256-GCM).
 *
 * Produces a fresh random salt (for KDF) and nonce (for GCM) on every call.
 * Two calls with the same password produce DIFFERENT outputs.
 */
export async function wrapDEK(
  dek: Uint8Array,
  password: string,
  salt?: Uint8Array,
  params?: KdfParams,
): Promise<WrappedKey> {
  const kdfSalt = salt ?? crypto.getRandomValues(new Uint8Array(16));
  const kdfParams = params ?? DEFAULT_KDF_PARAMS;
  const kek = await deriveKEK(password, kdfSalt, kdfParams);
  const nonce = crypto.getRandomValues(new Uint8Array(12));

  const wrapped = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv: nonce },
    kek,
    dek,
  );

  return {
    wrapped: new Uint8Array(wrapped),
    nonce,
    kdfSalt,
    kdfParams,
    dekVersion: 1,
  };
}

/**
 * Unwrap a DEK from its envelope.
 *
 * Throws:
 *   - "WrongPasswordError" if GCM authentication fails (wrong password)
 *   - Standard Error for other failures (tampered envelope, etc.)
 */
export async function unwrapDEK(
  wrapped: Uint8Array,
  nonce: Uint8Array,
  password: string,
  salt: Uint8Array,
  params: KdfParams,
): Promise<Uint8Array> {
  const kek = await deriveKEK(password, salt, params);

  try {
    const plain = await crypto.subtle.decrypt(
      { name: "AES-GCM", iv: nonce },
      kek,
      wrapped,
    );
    return new Uint8Array(plain);
  } catch (e: unknown) {
    if (e instanceof DOMException && e.name === "OperationError") {
      throw new WrongPasswordError();
    }
    throw e;
  }
}

// ── Section content encryption / decryption ─────────────────────────

/**
 * Encrypt a section's plaintext content with the DEK.
 *
 * Uses a FRESH random 12-byte nonce per call. Two calls with the same
 * plaintext produce DIFFERENT ciphertexts. The client MUST NOT re-encrypt
 * a section whose plaintext hasn't changed — send the existing ciphertext
 * as-is; otherwise the server's fingerprint comparison would detect a
 * false change.
 */
export async function encryptSection(
  dek: Uint8Array,
  plaintext: Uint8Array,
): Promise<EncryptedSection> {
  const key = await importDEK(dek);
  const nonce = crypto.getRandomValues(new Uint8Array(12));

  const ciphertext = await crypto.subtle.encrypt(
    { name: "AES-GCM", iv: nonce },
    key,
    plaintext,
  );

  return {
    ciphertext: new Uint8Array(ciphertext),
    nonce,
  };
}

/**
 * Decrypt a section's ciphertext with the DEK.
 *
 * Throws on GCM authentication failure (tampered data, wrong DEK).
 */
export async function decryptSection(
  dek: Uint8Array,
  ciphertext: Uint8Array,
  nonce: Uint8Array,
): Promise<Uint8Array> {
  const key = await importDEK(dek);

  const plain = await crypto.subtle.decrypt(
    { name: "AES-GCM", iv: nonce },
    key,
    ciphertext,
  );

  return new Uint8Array(plain);
}

/**
 * Derive a KEK from an invitation code (Crockford base32).
 *
 * Uses the same Argon2id params as password-derived KEKs so the invitee
 * can unwrap the DEK, then re-wrap under their own password.
 */
export async function deriveKEKFromCode(
  code: string,
  salt: Uint8Array,
  params: KdfParams,
): Promise<CryptoKey> {
  return deriveKEK(code, salt, params);
}

// ── Errors ─────────────────────────────────────────────────────────

export class WrongPasswordError extends Error {
  constructor() {
    super("Mot de passe incorrect — l'enveloppe n'a pas pu être déchiffrée");
    this.name = "WrongPasswordError";
  }
}

// ── Session manager ────────────────────────────────────────────────

/**
 * Module-level DEK holder — one per tab, zero persistence.
 *
 * DO NOT import this directly from React components; use the accessors below
 * so we can audit every read/write of the DEK.
 */
let _sessionDEK: Uint8Array | null = null;

export function setSessionDEK(dek: Uint8Array): void {
  if (_sessionDEK) {
    _sessionDEK.fill(0);
  }
  _sessionDEK = dek;
}

export function getSessionDEK(): Uint8Array | null {
  return _sessionDEK;
}

export function clearSessionDEK(): void {
  if (_sessionDEK) {
    _sessionDEK.fill(0);
    _sessionDEK = null;
  }
}

/**
 * Check whether the vault session is currently active
 * (i.e. the DEK is in memory).
 */
export function isVaultUnlocked(): boolean {
  return _sessionDEK !== null;
}

/**
 * Compute a stable, keyed digest of plaintext content for section fingerprinting.
 *
 * Uses HMAC-SHA256 with the DEK as key. This is deliberately keyed:
 * a bare SHA-256(content) would let anyone with read access to the database
 * confirm plaintext guesses ("Décision approuvée", "RAS", etc.) against the
 * stored digest. With the DEK as HMAC key, confirmation requires the key,
 * which the server never sees.
 *
 * Returns a 32-byte digest (SHA-256 output length).
 */
export async function sectionDigest(
  plaintext: Uint8Array,
  dek: Uint8Array,
): Promise<Uint8Array> {
  const key = await crypto.subtle.importKey(
    "raw",
    dek,
    { name: "HMAC", hash: "SHA-256" },
    false,
    ["sign"],
  );
  const digest = await crypto.subtle.sign("HMAC", key, plaintext);
  return new Uint8Array(digest);
}
