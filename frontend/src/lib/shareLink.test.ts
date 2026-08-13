/**
 * Tests for shareLink.ts — partage sécurisé du PV avec la direction.
 *
 * @vitest-environment node
 *
 * Invariants critiques :
 * - Le code de lecture n'est jamais transmis au serveur (l'enveloppe seule l'est)
 * - Wrap avec le code → unwrap avec le bon code → DEK identique
 * - Mauvais code → WrongPasswordError (jamais d'échec silencieux)
 * - Deux wraps différents (aléatoire) → enveloppes différentes
 * - Sections en clair (sans nonce) et chiffrées déchiffrées correctement
 */

import { describe, it, expect } from "vitest";
import { generateDEK, WrongPasswordError, encryptSection } from "./vault";
import {
  generateReadCode,
  wrapDEKForSharing,
  unwrapSharedDEK,
  decryptSharedSections,
  b64encode,
  b64decode,
  type SharedSection,
} from "./shareLink";

describe("generateReadCode", () => {
  it("produit 8 caractères de l'alphabet Crockford sans ambiguïté", () => {
    const code = generateReadCode();
    expect(code).toHaveLength(8);
    const alphabet = "ABCDEFGHJKMNPQRSTVWXYZ23456789";
    for (const c of code) {
      expect(alphabet).toContain(c);
    }
    // Jamais de caractères ambigus I/L/O/U
    expect(code).not.toMatch(/[ILOU]/);
  });

  it("deux codes successifs sont différents", () => {
    const a = generateReadCode();
    const b = generateReadCode();
    expect(a).not.toBe(b);
  });
});

describe("wrapDEKForSharing / unwrapSharedDEK", () => {
  it("round-trip : bon code → DEK identique", async () => {
    const dek = generateDEK();
    const code = generateReadCode();
    const { envelope } = await wrapDEKForSharing(dek, code);

    // L'enveloppe ne contient pas le code en clair
    expect(envelope).not.toContain(code);

    const recovered = await unwrapSharedDEK(envelope, code);
    expect(Buffer.from(recovered).equals(Buffer.from(dek))).toBe(true);
  });

  it("mauvais code → WrongPasswordError", async () => {
    const dek = generateDEK();
    const { envelope } = await wrapDEKForSharing(dek, generateReadCode());
    await expect(unwrapSharedDEK(envelope, "AAAAAAAA")).rejects.toThrow(WrongPasswordError);
  });

  it("enveloppe corrompue → erreur (jamais d'échec silencieux)", async () => {
    const dek = generateDEK();
    const { envelope } = await wrapDEKForSharing(dek, generateReadCode());
    const tampered = envelope.replace('"algo":"argon2id"', '"algo":"argon2idx"');
    await expect(unwrapSharedDEK(tampered, "AAAAAAAA")).rejects.toThrow();
  });

  it("deux wraps du même DEK produisent des enveloppes différentes", async () => {
    const dek = generateDEK();
    const code = "ABCD1234";
    const e1 = await wrapDEKForSharing(dek, code);
    const e2 = await wrapDEKForSharing(dek, code);
    expect(e1.envelope).not.toBe(e2.envelope);
  });
});

describe("b64 helpers", () => {
  it("round-trip b64", () => {
    const bytes = new Uint8Array([0, 1, 2, 250, 255, 128]);
    expect(Array.from(b64decode(b64encode(bytes)))).toEqual(Array.from(bytes));
  });
});

describe("decryptSharedSections", () => {
  it("déchiffre les sections chiffrées (nonce présent)", async () => {
    const dek = generateDEK();
    const plain = new TextEncoder().encode("Décision approuvée à l'unanimité");
    const { ciphertext, nonce } = await encryptSection(dek, plain);

    const sections: SharedSection[] = [{
      position: 0,
      title: "Décision",
      content: b64encode(ciphertext),
      nonce: b64encode(nonce),
    }];
    const out = await decryptSharedSections(dek, sections);
    expect(out).toHaveLength(1);
    expect(out[0].text).toBe("Décision approuvée à l'unanimité");
  });

  it("laisse les sections en clair (sans nonce) telles quelles", async () => {
    const dek = generateDEK();
    const sections: SharedSection[] = [{
      position: 0,
      title: "Sans coffre",
      content: b64encode(new TextEncoder().encode("texte en clair")),
      nonce: null,
    }];
    const out = await decryptSharedSections(dek, sections);
    expect(out[0].text).toBe("texte en clair");
  });
});
