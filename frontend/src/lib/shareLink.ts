/**
 * shareLink.ts — Partage sécurisé d'un PV avec la direction (lien + code).
 *
 * Flux :
 *   1. Créateur (coffre déverrouillé) : génère un code de lecture aléatoire,
 *      dérive une KEK du code (Argon2id, mêmes params que le coffre) et
 *      chiffre la DEK sous cette KEK → enveloppe JSON envoyée au serveur.
 *      Le code n'est JAMAIS transmis : il est affiché une fois et transmis
 *      à la direction par un canal séparé.
 *   2. Direction (sans compte) : ouvre /p/<token>, saisit le code →
 *      dérive la même KEK → unwrap de la DEK → déchiffre les sections
 *      partagées dans SON navigateur. Le serveur ne voit jamais le clair.
 */
import {
  DEFAULT_KDF_PARAMS,
  KdfParams,
  decryptSection,
  deriveKEKFromCode,
  unwrapDEK,
  wrapDEK,
} from "./vault";

// ── Helpers b64 ───────────────────────────────────────────────────

export function b64encode(bytes: Uint8Array): string {
  let bin = "";
  for (let i = 0; i < bytes.length; i++) bin += String.fromCharCode(bytes[i]);
  return btoa(bin);
}

export function b64decode(b64: string): Uint8Array {
  const bin = atob(b64);
  const out = new Uint8Array(bin.length);
  for (let i = 0; i < bin.length; i++) out[i] = bin.charCodeAt(i);
  return out;
}

export interface ShareEnvelope {
  algo: "argon2id";
  salt: string; // b64
  nonce: string; // b64
  wrapped: string; // b64
  params: KdfParams;
}

export interface SharedSection {
  position: number;
  title: string;
  content: string; // b64 ciphertext (ou clair si coffre inactif)
  nonce: string | null; // b64
}

// ── Code de lecture ───────────────────────────────────────────────

const CODE_ALPHABET = "ABCDEFGHJKMNPQRSTVWXYZ23456789"; // Crockford, sans I/L/O/U

/** Code de lecture : 8 caractères lisibles (~40 bits d'entropie). */
export function generateReadCode(length = 8): string {
  const alphabetLen = CODE_ALPHABET.length
  // Rejection sampling : 256 % 30 = 16 → sans rejet, les indices 0..15
  // sortiraient 9 fois sur 256 contre 8 pour 16..29 (biais modulo). On
  // n'accepte que les octets < 240 (multiple de 30 le plus proche) :
  // chaque caractère est alors parfaitement uniforme.
  const limit = 256 - (256 % alphabetLen)
  let code = ""
  while (code.length < length) {
    const rnd = crypto.getRandomValues(new Uint8Array(length - code.length))
    for (let i = 0; i < rnd.length; i++) {
      if (rnd[i] < limit) code += CODE_ALPHABET[rnd[i] % alphabetLen]
    }
  }
  return code
}

/**
 * Chiffre la DEK sous un code de lecture.
 * Retourne { code, envelope } — le code reste côté client.
 */
export async function wrapDEKForSharing(
  dek: Uint8Array,
  code: string,
): Promise<{ code: string; envelope: string }> {
  const wrapped = await wrapDEK(dek, code);
  const envelope: ShareEnvelope = {
    algo: "argon2id",
    salt: b64encode(wrapped.kdfSalt),
    nonce: b64encode(wrapped.nonce),
    wrapped: b64encode(wrapped.wrapped),
    params: wrapped.kdfParams,
  };
  return { code, envelope: JSON.stringify(envelope) };
}

/**
 * Déchiffre la DEK depuis l'enveloppe avec le code de lecture.
 * Lance WrongPasswordError si le code est incorrect.
 */
export async function unwrapSharedDEK(
  envelopeJson: string,
  code: string,
): Promise<Uint8Array> {
  const env: ShareEnvelope = JSON.parse(envelopeJson);
  return unwrapDEK(
    b64decode(env.wrapped),
    b64decode(env.nonce),
    code,
    b64decode(env.salt),
    env.params ?? DEFAULT_KDF_PARAMS,
  );
}

/**
 * Déchiffre les sections partagées avec la DEK retrouvée.
 * Retourne [{ position, title, text }] — clair côté client uniquement.
 */
export async function decryptSharedSections(
  dek: Uint8Array,
  sections: SharedSection[],
): Promise<{ position: number; title: string; text: string }[]> {
  const out: { position: number; title: string; text: string }[] = [];
  for (const s of sections) {
    if (s.nonce) {
      const plain = await decryptSection(dek, b64decode(s.content), b64decode(s.nonce));
      out.push({ position: s.position, title: s.title, text: new TextDecoder().decode(plain) });
    } else {
      // Section en clair (coffre inactif) — le contenu est du texte brut encodé
      out.push({ position: s.position, title: s.title, text: new TextDecoder().decode(b64decode(s.content)) });
    }
  }
  return out;
}

/** Dérive la KEK depuis le code (pour vérification éventuelle). */
export function deriveReadKEK(code: string, salt: Uint8Array, params: KdfParams = DEFAULT_KDF_PARAMS) {
  return deriveKEKFromCode(code, salt, params);
}
