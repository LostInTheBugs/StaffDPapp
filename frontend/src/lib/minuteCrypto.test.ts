/**
 * Tests for minuteCrypto.ts — vault-aware minute operations.
 *
 * @vitest-environment node
 *
 * Key invariants tested:
 *  - prepareSectionsForSave: unchanged plaintext → same ciphertext + nonce
 *  - prepareSectionsForSave: changed plaintext → new nonce + new digest
 *  - decryptSectionsForDisplay: round-trip preserves exact content (accents, newlines)
 *  - preparePreviewForPdf: decrypted sections keep visibility 'partage'
 *  - preparePreviewForPdf: locked vault → VaultLockedError (never empty/ciphertext)
 *  - needsUnlock: detects encrypted sections without DEK
 */

import { describe, it, expect, afterEach } from "vitest";
import {
  generateDEK,
  encryptSection,
  sectionDigest,
  setSessionDEK,
  clearSessionDEK,
} from "./vault";
import {
  decryptSectionsForDisplay,
  prepareSectionsForSave,
  preparePreviewForPdf,
  needsUnlock,
  previewNeedsDecryption,
  VaultLockedError,
  type ApiSection,
  type ResolvedSection,
  type DirectionPreview,
} from "./minuteCrypto";

const encoder = new TextEncoder();
const decoder = new TextDecoder();

function b64(str: string): string {
  let binary = "";
  encoder.encode(str).forEach((b) => (binary += String.fromCharCode(b)));
  return Buffer.from(binary, "binary").toString("base64");
}

function fromB64(b64str: string): string {
  return decoder.decode(Buffer.from(b64str, "base64"));
}

afterEach(() => {
  clearSessionDEK();
});

// ═══════════════════════════════════════════════════════════════════
// Helpers to create encrypted API sections
// ═══════════════════════════════════════════════════════════════════

async function makeEncryptedApiSection(
  dek: Uint8Array,
  plaintext: string,
  position: number,
  title: string,
  visibility: string,
): Promise<ApiSection> {
  const pt = encoder.encode(plaintext);
  const enc = await encryptSection(dek, pt);
  const digest = await sectionDigest(pt, dek);

  return {
    id: position + 1,
    position,
    title,
    visibility,
    content: Buffer.from(enc.ciphertext).toString("base64"),
    nonce: Buffer.from(enc.nonce).toString("base64"),
    content_digest: Buffer.from(digest).toString("base64"),
  };
}

function makePlainApiSection(
  plaintext: string,
  position: number,
  title: string,
  visibility: string,
): ApiSection {
  return {
    id: position + 1,
    position,
    title,
    visibility,
    content: b64(plaintext),
    nonce: null,
    content_digest: null,
  };
}

// ═══════════════════════════════════════════════════════════════════
// 1. decryptSectionsForDisplay
// ═══════════════════════════════════════════════════════════════════

describe("decryptSectionsForDisplay", () => {
  it("déchiffre les sections chiffrées quand le coffre est déverrouillé", async () => {
    const dek = generateDEK();
    setSessionDEK(dek);

    const sections: ApiSection[] = [
      await makeEncryptedApiSection(dek, "Décision approuvée à l'unanimité", 0, "Résolution", "interne"),
      await makeEncryptedApiSection(dek, "Prochaines étapes : négociation salariale", 1, "Plan d'action", "partage"),
    ];

    const resolved = await decryptSectionsForDisplay(sections);

    expect(resolved.length).toBe(2);
    expect(resolved[0].content).toBe("Décision approuvée à l'unanimité");
    expect(resolved[1].content).toBe("Prochaines étapes : négociation salariale");
    // Both should carry encrypted envelope
    expect(resolved[0]._encrypted).not.toBeNull();
    expect(resolved[1]._encrypted).not.toBeNull();
    // Original plaintext should match current
    expect(resolved[0]._originalPlaintext).toBe(resolved[0].content);
  });

  it("round-trip complet chiffrement → déchiffrement redonne le clair exact, y compris accents et sauts de ligne", async () => {
    const dek = generateDEK();
    setSessionDEK(dek);

    const originalText = "Résumé :\n\n- Étape 1 : vérification des créances\n- Étape 2 : réaffectation du personnel (Müller, Schmit)\n\nCoût total estimé : 42 500 €.";

    const sections: ApiSection[] = [
      await makeEncryptedApiSection(dek, originalText, 0, "Résumé financier", "interne"),
    ];

    const resolved = await decryptSectionsForDisplay(sections);

    // Exact match, byte-perfect round-trip
    expect(resolved[0].content).toBe(originalText);

    // Now save unchanged → should reuse same envelope
    const forSave = await prepareSectionsForSave(resolved);
    expect(forSave[0].content).toBe(sections[0].content);
    expect(forSave[0].nonce).toBe(sections[0].nonce);
    expect(forSave[0].content_digest).toBe(sections[0].content_digest);
  });

  it("les sections en clair (sans coffre) sont simplement décodées en base64", async () => {
    // No DEK set
    const sections: ApiSection[] = [
      makePlainApiSection("Contenu en clair", 0, "Section 1", "interne"),
      makePlainApiSection("Autre contenu", 1, "Section 2", "partage"),
    ];

    const resolved = await decryptSectionsForDisplay(sections);

    expect(resolved[0].content).toBe("Contenu en clair");
    expect(resolved[1].content).toBe("Autre contenu");
    expect(resolved[0]._encrypted).toBeNull();
    expect(resolved[1]._encrypted).toBeNull();
  });

  it("coffre verrouillé : sections chiffrées → contenu vide (pas d'erreur, le composant doit proposer le déverrouillage)", async () => {
    // No DEK in memory
    const dek = generateDEK();
    const sections: ApiSection[] = [
      await makeEncryptedApiSection(dek, "Secret", 0, "S1", "interne"),
      makePlainApiSection("Pas secret", 1, "S2", "partage"),
    ];

    const resolved = await decryptSectionsForDisplay(sections);

    // Encrypted section: empty content but _encrypted envelope preserved
    expect(resolved[0].content).toBe("");
    expect(resolved[0]._encrypted).not.toBeNull();
    // Plaintext section: still decoded
    expect(resolved[1].content).toBe("Pas secret");
    expect(resolved[1]._encrypted).toBeNull();
  });
});

// ═══════════════════════════════════════════════════════════════════
// 2. prepareSectionsForSave
// ═══════════════════════════════════════════════════════════════════

describe("prepareSectionsForSave", () => {
  it("section inchangée → même ciphertext et même nonce (pas de rechiffrement inutile)", async () => {
    const dek = generateDEK();
    setSessionDEK(dek);

    const originalPlaintext = "Décision approuvée à l'unanimité";
    const sections: ApiSection[] = [
      await makeEncryptedApiSection(dek, originalPlaintext, 0, "Résolution", "interne"),
    ];

    // Load (decrypt)
    const resolved = await decryptSectionsForDisplay(sections);

    // Don't modify
    const forSave = await prepareSectionsForSave(resolved);

    // Must reuse the exact same ciphertext, nonce, and digest
    expect(forSave[0].content).toBe(sections[0].content);
    expect(forSave[0].nonce).toBe(sections[0].nonce);
    expect(forSave[0].content_digest).toBe(sections[0].content_digest);
  });

  it("section modifiée → nouveau nonce ET nouveau digest", async () => {
    const dek = generateDEK();
    setSessionDEK(dek);

    const sections: ApiSection[] = [
      await makeEncryptedApiSection(dek, "Version originale", 0, "S1", "interne"),
    ];

    const resolved = await decryptSectionsForDisplay(sections);

    // Modify the content
    resolved[0].content = "Version modifiée avec des ajouts substantiels";

    const forSave = await prepareSectionsForSave(resolved);

    // Content must differ
    expect(forSave[0].content).not.toBe(sections[0].content);
    // Nonce must differ (fresh random)
    expect(forSave[0].nonce).not.toBe(sections[0].nonce);
    // Digest must differ (different plaintext)
    expect(forSave[0].content_digest).not.toBe(sections[0].content_digest);
    // But nonce and digest must be present
    expect(forSave[0].nonce).toBeTruthy();
    expect(forSave[0].content_digest).toBeTruthy();
  });

  it("plusieurs sections : seule la section modifiée est rechiffrée, l'autre inchangée", async () => {
    const dek = generateDEK();
    setSessionDEK(dek);

    const apiSections: ApiSection[] = [
      await makeEncryptedApiSection(dek, "Section A — inchangée", 0, "SA", "interne"),
      await makeEncryptedApiSection(dek, "Section B — originale", 1, "SB", "partage"),
    ];

    const resolved = await decryptSectionsForDisplay(apiSections);

    // Only modify section B
    resolved[1].content = "Section B — modifiée après révision";

    const forSave = await prepareSectionsForSave(resolved);

    // Section A: unchanged → reuse
    expect(forSave[0].content).toBe(apiSections[0].content);
    expect(forSave[0].nonce).toBe(apiSections[0].nonce);
    expect(forSave[0].content_digest).toBe(apiSections[0].content_digest);

    // Section B: changed → new values
    expect(forSave[1].content).not.toBe(apiSections[1].content);
    expect(forSave[1].nonce).not.toBe(apiSections[1].nonce);
    expect(forSave[1].content_digest).not.toBe(apiSections[1].content_digest);
    expect(forSave[1].nonce).toBeTruthy();
    expect(forSave[1].content_digest).toBeTruthy();
  });

  it("sections en clair (vault désactivé) : simplement encodées base64", async () => {
    const sections: ResolvedSection[] = [
      {
        id: 1,
        position: 0,
        title: "S1",
        visibility: "interne",
        content: "Texte en clair ~ accentué",
        _encrypted: null,
        _originalPlaintext: "Texte en clair ~ accentué",
      },
    ];

    const forSave = await prepareSectionsForSave(sections);

    expect(forSave[0].nonce).toBeNull();
    expect(forSave[0].content_digest).toBeNull();
    // Verify base64 round-trip
    expect(fromB64(forSave[0].content)).toBe("Texte en clair ~ accentué");
  });

  it("coffre verrouillé : prepareSectionsForSave lève VaultLockedError", async () => {
    // No DEK set
    const sections: ResolvedSection[] = [
      {
        id: 1,
        position: 0,
        title: "S1",
        visibility: "interne",
        content: "modifié",
        _encrypted: { content: "old-ciphertext-b64", nonce: "old-nonce-b64", content_digest: "old-digest-b64" },
        _originalPlaintext: "original",
      },
    ];

    await expect(prepareSectionsForSave(sections)).rejects.toThrow(VaultLockedError);
  });
});

// ═══════════════════════════════════════════════════════════════════
// 3. preparePreviewForPdf
// ═══════════════════════════════════════════════════════════════════

describe("preparePreviewForPdf", () => {
  it("les sections déchiffrées conservent visibility: 'partage'", async () => {
    const dek = generateDEK();
    setSessionDEK(dek);

    const encryptedText = "Bilan financier approuvé";
    const pt = encoder.encode(encryptedText);
    const enc = await encryptSection(dek, pt);

    const preview: DirectionPreview = {
      minute_id: 1,
      meeting_title: "Réunion test",
      validated_by_name: null,
      validated_at: null,
      generated_at: "2026-01-01T00:00:00Z",
      sections: [
        {
          position: 0,
          title: "Bilan",
          content: Buffer.from(enc.ciphertext).toString("base64"),
          visibility: "partage",
          nonce: Buffer.from(enc.nonce).toString("base64"),
        },
      ],
    };

    const result = await preparePreviewForPdf(preview);

    expect(result.sections.length).toBe(1);
    // visibility MUST be 'partage' — fail-closed filter in pdfExport needs it
    expect(result.sections[0].visibility).toBe("partage");
    // Content should be decrypted and re-encoded as base64
    const decodedFromB64 = fromB64(result.sections[0].content);
    expect(decodedFromB64).toBe(encryptedText);
    // nonce must be nulled out (no longer encrypted)
    expect(result.sections[0].nonce).toBeNull();
  });

  it("coffre verrouillé : preparePreviewForPdf lève VaultLockedError (jamais de ciphertext ou de liste vide)", async () => {
    // No DEK
    const preview: DirectionPreview = {
      minute_id: 1,
      meeting_title: "Test",
      validated_by_name: null,
      validated_at: null,
      generated_at: "2026-01-01T00:00:00Z",
      sections: [
        {
          position: 0,
          title: "S1",
          content: "some-ciphertext-b64",
          visibility: "partage",
          nonce: "some-nonce-b64",
        },
      ],
    };

    await expect(preparePreviewForPdf(preview)).rejects.toThrow(VaultLockedError);
  });

  it("les sections déjà en clair dans la preview (vault désactivé) sont simplement passées à travers", async () => {
    const dek = generateDEK();
    setSessionDEK(dek);

    const preview: DirectionPreview = {
      minute_id: 1,
      meeting_title: "Test",
      validated_by_name: null,
      validated_at: null,
      generated_at: "2026-01-01T00:00:00Z",
      sections: [
        {
          position: 0,
          title: "S1",
          content: b64("Contenu en clair de la preview"),
          visibility: "partage",
          nonce: null,
        },
      ],
    };

    const result = await preparePreviewForPdf(preview);
    expect(result.sections[0].visibility).toBe("partage");
    expect(fromB64(result.sections[0].content)).toBe("Contenu en clair de la preview");
  });
});

// ═══════════════════════════════════════════════════════════════════
// 4. needsUnlock
// ═══════════════════════════════════════════════════════════════════

describe("needsUnlock", () => {
  it("retourne true si des sections sont chiffrées et le coffre est verrouillé", async () => {
    const dek = generateDEK();
    const sections: ApiSection[] = [
      await makeEncryptedApiSection(dek, "secret", 0, "S1", "interne"),
    ];
    // No DEK in session
    expect(needsUnlock(sections)).toBe(true);
  });

  it("retourne false si des sections sont chiffrées mais le coffre est déverrouillé", async () => {
    const dek = generateDEK();
    setSessionDEK(dek);
    const sections: ApiSection[] = [
      await makeEncryptedApiSection(dek, "secret", 0, "S1", "interne"),
    ];
    expect(needsUnlock(sections)).toBe(false);
  });

  it("retourne false si aucune section n'est chiffrée", () => {
    const sections: ApiSection[] = [
      makePlainApiSection("clair", 0, "S1", "interne"),
    ];
    expect(needsUnlock(sections)).toBe(false);
  });
});

// ═══════════════════════════════════════════════════════════════════
// 5. previewNeedsDecryption
// ═══════════════════════════════════════════════════════════════════

describe("previewNeedsDecryption", () => {
  it("détecte les sections chiffrées dans une preview", async () => {
    const dek = generateDEK();
    const pt = encoder.encode("test");
    const enc = await encryptSection(dek, pt);

    const preview: DirectionPreview = {
      minute_id: 1,
      meeting_title: "T",
      validated_by_name: null,
      validated_at: null,
      generated_at: "2026-01-01T00:00:00Z",
      sections: [
        {
          position: 0,
          title: "S1",
          content: Buffer.from(enc.ciphertext).toString("base64"),
          visibility: "partage",
          nonce: Buffer.from(enc.nonce).toString("base64"),
        },
      ],
    };

    expect(previewNeedsDecryption(preview)).toBe(true);
  });

  it("retourne false si toutes les sections sont en clair", () => {
    const preview: DirectionPreview = {
      minute_id: 1,
      meeting_title: "T",
      validated_by_name: null,
      validated_at: null,
      generated_at: "2026-01-01T00:00:00Z",
      sections: [
        {
          position: 0,
          title: "S1",
          content: b64("clair"),
          visibility: "partage",
          nonce: null,
        },
      ],
    };

    expect(previewNeedsDecryption(preview)).toBe(false);
  });
});
