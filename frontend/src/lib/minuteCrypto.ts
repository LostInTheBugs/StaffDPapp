/**
 * minuteCrypto.ts — Non-React logic for vault-aware minute operations.
 *
 * Pure functions, zero DOM/React dependency — fully testable in Node
 * via vitest. Consumed by Minutes.tsx to encrypt/decrypt section
 * content transparently when the vault is active.
 *
 * Design invariants:
 *  - Unchanged sections MUST NOT be re-encrypted. The server's fingerprint
 *    comparison uses content_digest (HMAC of plaintext, stable), but
 *    re-encrypting unnecessarily still rewrites the database for no reason
 *    and destroys auditability.
 *  - Sections encrypted with the vault always carry a nonce AND a
 *    content_digest. The server's encryption guard rejects any that don't.
 *  - The direction preview must NEVER produce a PDF with ciphertext or
 *    missing content. If the vault is locked, preview preparation throws.
 */

import {
  encryptSection,
  decryptSection,
  sectionDigest,
  getSessionDEK,
  type EncryptedSection,
} from "./vault";
import type {
  DirectionPreview,
  DirectionPreviewSection,
} from "./pdfExport";

// Re-export the pdfExport types for convenience
export type { DirectionPreview, DirectionPreviewSection };

// ── Types ──────────────────────────────────────────────────────────

/**
 * A section as it arrives from the API (base64-encoded binary fields).
 * `content` is base64 of either plaintext (UTF-8) or AES-GCM ciphertext.
 */
export interface ApiSection {
  id: number | null;
  position: number;
  title: string;
  visibility: string;
  content: string; // base64
  nonce: string | null; // base64, null if plaintext
  content_digest: string | null; // base64, null if plaintext
}

/**
 * A section resolved for display — always holds plaintext in `content`.
 * Carries the original encrypted envelope so prepareSectionsForSave()
 * can reuse it when the plaintext hasn't changed.
 */
export interface ResolvedSection {
  id: number | null;
  position: number;
  title: string;
  visibility: string;
  content: string; // plaintext
  /** Original encrypted envelope, preserved for save comparison. */
  _encrypted: {
    content: string; // base64 ciphertext
    nonce: string; // base64 nonce
    content_digest: string; // base64 HMAC
  } | null;
  /** Plaintext at load time — compared on save to decide re-encryption. */
  _originalPlaintext: string;
}

/**
 * A section ready to send to the API (PUT /sections).
 * `content` is always base64-encoded (plaintext or ciphertext).
 * `nonce` and `content_digest` are set iff the section is encrypted.
 */
export interface SectionForSave {
  position: number;
  title: string;
  visibility: string;
  content: string; // base64
  nonce: string | null;
  content_digest: string | null;
}

// ── Errors ─────────────────────────────────────────────────────────

export class VaultLockedError extends Error {
  constructor() {
    super(
      "Le coffre est verrouillé. Déverrouillez-le pour accéder au contenu chiffré.",
    );
    this.name = "VaultLockedError";
  }
}

// ── Helpers ────────────────────────────────────────────────────────

const encoder = new TextEncoder();
const decoder = new TextDecoder();

function b64ToBytes(b64: string): Uint8Array {
  const binary = atob(b64);
  const bytes = new Uint8Array(binary.length);
  for (let i = 0; i < binary.length; i++) {
    bytes[i] = binary.charCodeAt(i);
  }
  return bytes;
}

function bytesToB64(bytes: Uint8Array): string {
  let binary = "";
  bytes.forEach((b) => (binary += String.fromCharCode(b)));
  return btoa(binary);
}

function getDekOrThrow(): Uint8Array {
  const dek = getSessionDEK();
  if (!dek) throw new VaultLockedError();
  return dek;
}

// ── Public API ─────────────────────────────────────────────────────

/**
 * Decrypt all sections that carry a nonce.
 *
 * Async — called to populate plaintext for display.
 * Sections without a nonce are just base64-decoded.
 *
 * If the vault is locked and a section has a nonce, its content is set
 * to "" but the encrypted envelope is preserved. The caller should check
 * with needsUnlock() and prompt for unlock before displaying content.
 */
export async function decryptSectionsForDisplay(
  apiSections: ApiSection[],
): Promise<ResolvedSection[]> {
  const dek = getSessionDEK();

  const results: ResolvedSection[] = [];

  for (const sec of apiSections) {
    const hasNonce = sec.nonce && sec.nonce.length > 0;

    let plaintext: string;
    let encrypted: ResolvedSection["_encrypted"] = null;

    if (hasNonce) {
      if (!dek) {
        // Vault locked, encrypted content → empty placeholder
        plaintext = "";
        encrypted = {
          content: sec.content,
          nonce: sec.nonce!,
          content_digest: sec.content_digest || "",
        };
      } else {
        // Decrypt
        const ciphertextBytes = b64ToBytes(sec.content);
        const nonceBytes = b64ToBytes(sec.nonce!);
        const decrypted = await decryptSection(dek, ciphertextBytes, nonceBytes);
        plaintext = decoder.decode(decrypted);
        encrypted = {
          content: sec.content,
          nonce: sec.nonce!,
          content_digest: sec.content_digest || "",
        };
      }
    } else {
      // Plaintext section — just base64-decode
      plaintext = sec.content ? decoder.decode(b64ToBytes(sec.content)) : "";
    }

    results.push({
      id: sec.id,
      position: sec.position,
      title: sec.title,
      visibility: sec.visibility || "interne",
      content: plaintext,
      _encrypted: encrypted,
      _originalPlaintext: plaintext,
    });
  }

  return results;
}

/**
 * Check whether any API section needs decryption (has a nonce) and the
 * vault is locked (no DEK in memory).
 */
export function needsUnlock(apiSections: ApiSection[]): boolean {
  const hasEncrypted = apiSections.some(
    (s) => s.nonce && s.nonce.length > 0,
  );
  return hasEncrypted && !getSessionDEK();
}

/**
 * Prepare sections for save.
 *
 * For encrypted sections: if the plaintext hasn't changed, reuse the
 * existing ciphertext, nonce, and digest. If changed, re-encrypt with a
 * fresh random nonce and compute a new digest.
 *
 * For plaintext sections: just base64-encode (vault disabled).
 */
export async function prepareSectionsForSave(
  sections: ResolvedSection[],
): Promise<SectionForSave[]> {
  const dek = getSessionDEK();

  const results: SectionForSave[] = [];

  for (const sec of sections) {
    if (sec._encrypted && dek) {
      // Encrypted section — compare with original
      if (sec.content === sec._originalPlaintext) {
        // Unchanged → reuse existing envelope
        results.push({
          position: sec.position,
          title: sec.title,
          visibility: sec.visibility,
          content: sec._encrypted.content,
          nonce: sec._encrypted.nonce,
          content_digest: sec._encrypted.content_digest,
        });
      } else {
        // Changed → re-encrypt
        const plaintextBytes = encoder.encode(sec.content);
        const encrypted: EncryptedSection = await encryptSection(
          dek,
          plaintextBytes,
        );
        const digest = await sectionDigest(plaintextBytes, dek);

        results.push({
          position: sec.position,
          title: sec.title,
          visibility: sec.visibility,
          content: bytesToB64(encrypted.ciphertext),
          nonce: bytesToB64(encrypted.nonce),
          content_digest: bytesToB64(digest),
        });
      }
    } else if (sec._encrypted && !dek) {
      // Vault locked — can't re-encrypt, but should not happen because
      // the UI must require unlock before editing. Throw explicitly.
      throw new VaultLockedError();
    } else {
      // Plaintext section (vault disabled)
      results.push({
        position: sec.position,
        title: sec.title,
        visibility: sec.visibility,
        content: bytesToB64(encoder.encode(sec.content)),
        nonce: null,
        content_digest: null,
      });
    }
  }

  return results;
}

/**
 * Prepare a direction preview for PDF export.
 *
 * Decrypts every section that carries a nonce (vault-enabled org).
 * Preserves visibility: 'partage' on every returned section so the
 * fail-closed filter in pdfExport doesn't discard everything.
 *
 * THROWS VaultLockedError if the vault is locked — the caller MUST
 * not proceed to PDF generation.
 */
export async function preparePreviewForPdf(
  preview: DirectionPreview,
): Promise<DirectionPreview> {
  const dek = getDekOrThrow();

  const decryptedSections: DirectionPreviewSection[] = [];

  for (const sec of preview.sections) {
    if (sec.nonce && sec.nonce.length > 0) {
      // Encrypted section — decrypt
      const ciphertextBytes = b64ToBytes(sec.content);
      const nonceBytes = b64ToBytes(sec.nonce);
      const decrypted = await decryptSection(dek, ciphertextBytes, nonceBytes);
      const plaintext = decoder.decode(decrypted);

      decryptedSections.push({
        position: sec.position,
        title: sec.title,
        content: bytesToB64(encoder.encode(plaintext)), // re-encode as base64 plaintext
        visibility: "partage", // preserve the marker for fail-closed filter
        nonce: null, // explicitly no longer encrypted
      });
    } else {
      // Already plaintext
      decryptedSections.push({
        position: sec.position,
        title: sec.title,
        content: sec.content,
        visibility: "partage", // preserve the marker
        nonce: null,
      });
    }
  }

  return {
    ...preview,
    sections: decryptedSections,
  };
}

/**
 * Check if a direction preview has encrypted sections that would need
 * decryption before PDF export.
 */
export function previewNeedsDecryption(preview: DirectionPreview): boolean {
  return preview.sections.some(
    (s) => s.nonce && s.nonce.length > 0,
  );
}
