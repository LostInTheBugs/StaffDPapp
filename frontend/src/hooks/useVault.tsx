import {
  createContext,
  useContext,
  useState,
  useEffect,
  useCallback,
  useRef,
  type ReactNode,
} from "react";
import { useAuth } from "./useAuth";
import * as api from "../api/client";
import type { VaultEnvelope } from "../api/client";
import {
  wrapDEK,
  unwrapDEK,
  generateDEK,
  generateRecoveryKey,
  wrapDEKWithRecoveryKey,
  unwrapDEKWithRecoveryKey,
  deriveKEKFromCode,
  setSessionDEK,
  getSessionDEK,
  clearSessionDEK,
  isVaultUnlocked,
  DEFAULT_KDF_PARAMS,
} from "../lib/vault";
import {
  recordActivity,
  shouldLock,
  lockVault,
  markUnlocked,
  normalizeCode,
  type VaultStatus,
} from "../lib/vaultSession";

// ── Types ──────────────────────────────────────────────────────────

interface VaultContextType {
  /** Current vault status: disabled, locked, or unlocked. */
  status: VaultStatus;
  /** True when the DEK is in memory and the vault is ready to use. */
  isUnlocked: boolean;
  /** Fetch vault status from the server. */
  refreshStatus: () => Promise<void>;
  /**
   * Attempt to unlock the vault with a password.
   * Throws WrongPasswordError on wrong password.
   */
  unlock: (password: string) => Promise<void>;
  /** Lock the vault and clear the DEK from memory. */
  lock: () => void;
  /**
   * Create the vault for the organization.
   * Generates a DEK, wraps it under the user's password, and POSTs to /api/vault.
   */
  createVault: (password: string) => Promise<void>;
  /**
   * Wrap the DEK under a code-derived KEK (for invitation envelopes).
   * Returns the envelope. Vault must be unlocked.
   */
  wrapForCode: (code: string) => Promise<VaultEnvelope>;
  /**
   * Unwrap a DEK from an invitation code, re-wrap under a password.
   * Used during /join to exchange the invitation envelope for a user envelope.
   */
  exchangeCodeForPassword: (
    code: string,
    password: string,
    envelope: api.VaultKeyResponse,
  ) => Promise<VaultEnvelope>;
  /** DEK version currently loaded (null if not unlocked). */
  dekVersion: number | null;
  /** True when a recovery envelope is stored server-side. */
  recoveryEnabled: boolean;
  /**
   * Unlock the vault with the recovery key (PBKDF2, no Argon2).
   * Throws WrongPasswordError on wrong key.
   */
  unlockWithRecoveryKey: (recoveryKey: string) => Promise<void>;
  /**
   * Wrap the current DEK under a NEW recovery key, store the envelope
   * server-side and return the key to display ONCE. Vault must be unlocked.
   */
  setRecoveryKey: () => Promise<string>;
  /** Revoke the recovery key (deletes the envelope server-side). */
  revokeRecoveryKey: () => Promise<void>;
  /**
   * Change the vault password: re-wraps the DEK under the new password
   * (PUT /api/vault/key). Vault must be unlocked.
   */
  changePassword: (newPassword: string) => Promise<void>;
}

const VaultContext = createContext<VaultContextType | null>(null);

const AUTO_LOCK_CHECK_MS = 15_000; // check every 15 seconds

// ── Provider ───────────────────────────────────────────────────────

export function VaultProvider({ children }: { children: ReactNode }) {
  const { token } = useAuth();

  const [vaultEnabled, setVaultEnabled] = useState(false);
  const [hasOwnKey, setHasOwnKey] = useState(false);
  const [dekVersion, setDekVersion] = useState<number | null>(null);

  // Periodic auto-lock check
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // ── Status derivation ──────────────────────────────────────────

  const computeCurrentStatus = useCallback((): VaultStatus => {
    if (!vaultEnabled) return "disabled";
    if (!hasOwnKey) return "disabled";
    return isVaultUnlocked() ? "unlocked" : "locked";
  }, [vaultEnabled, hasOwnKey]);

  // ── Auto-lock timer (ticks every 15s) ─────────────────────────

  useEffect(() => {
    intervalRef.current = setInterval(() => {
      if (shouldLock(vaultEnabled)) {
        lockVault();
        // Force React re-render for status update
        setDekVersion(null);
      }
    }, AUTO_LOCK_CHECK_MS);
    return () => {
      if (intervalRef.current) clearInterval(intervalRef.current);
    };
  }, [vaultEnabled]);

  // ── Lock on logout (clear DEK when token goes away) ─────────────

  useEffect(() => {
    if (!token) {
      clearSessionDEK();
      setVaultEnabled(false);
      setHasOwnKey(false);
      setDekVersion(null);
    }
  }, [token]);

  // ── Lock on component unmount ──────────────────────────────────

  useEffect(() => {
    return () => {
      clearSessionDEK();
    };
  }, []);

  // ── Activity heartbeat ────────────────────────────────────────

  useEffect(() => {
    const onActivity = () => recordActivity();
    window.addEventListener("mousemove", onActivity, { passive: true });
    window.addEventListener("keydown", onActivity, { passive: true });
    window.addEventListener("click", onActivity, { passive: true });
    window.addEventListener("touchstart", onActivity, { passive: true });
    return () => {
      window.removeEventListener("mousemove", onActivity);
      window.removeEventListener("keydown", onActivity);
      window.removeEventListener("click", onActivity);
      window.removeEventListener("touchstart", onActivity);
    };
  }, []);

  // ── refreshStatus ─────────────────────────────────────────────

  const refreshStatus = useCallback(async () => {
    try {
      const s = await api.getVaultStatus();
      setVaultEnabled(s.enabled);
      setHasOwnKey(s.has_key);
      setRecoveryEnabled(Boolean(s.recovery_enabled));
      if (isVaultUnlocked()) {
        setDekVersion(s.dek_version);
      }
    } catch {
      // Server might not have vault yet, or 404 — vault is disabled
      setVaultEnabled(false);
      setHasOwnKey(false);
    }
  }, []);

  // Fetch status on mount (when token present)
  useEffect(() => {
    if (token) refreshStatus();
  }, [token, refreshStatus]);

  // ── unlock ────────────────────────────────────────────────────

  const unlock = useCallback(async (password: string) => {
    const keyResp = await api.getVaultKey();
    // keyResp.kdf_params is a JSON string from the server
    const params = JSON.parse(keyResp.kdf_params);

    // Decode base64 fields
    const wrapped = Uint8Array.from(atob(keyResp.wrapped_dek), (c) =>
      c.charCodeAt(0),
    );
    const nonce = Uint8Array.from(atob(keyResp.nonce), (c) =>
      c.charCodeAt(0),
    );
    const salt = Uint8Array.from(atob(keyResp.kdf_salt), (c) =>
      c.charCodeAt(0),
    );

    const dek = await unwrapDEK(wrapped, nonce, password, salt, params);
    setSessionDEK(dek);
    markUnlocked();
    setDekVersion(keyResp.dek_version);
  }, []);

  // ── lock ──────────────────────────────────────────────────────

  const lock = useCallback(() => {
    lockVault();
    setDekVersion(null);
  }, []);

  // ── createVault ───────────────────────────────────────────────

  const createVault = useCallback(async (password: string) => {
    const dek = generateDEK();
    const envelope = await wrapDEK(dek, password);
    setSessionDEK(dek);

    await api.createVault({
      wrapped_dek: btoa(
        String.fromCharCode(...envelope.wrapped),
      ),
      nonce: btoa(String.fromCharCode(...envelope.nonce)),
      kdf_salt: btoa(String.fromCharCode(...envelope.kdfSalt)),
      kdf_params: JSON.stringify(envelope.kdfParams),
    });

    markUnlocked();
    setVaultEnabled(true);
    setHasOwnKey(true);
    setDekVersion(1);
  }, []);

  // ── wrapForCode ───────────────────────────────────────────────

  const wrapForCode = useCallback(async (code: string): Promise<VaultEnvelope> => {
    const dek = getSessionDEK();
    if (!dek) throw new Error("Vault must be unlocked to wrap for invitation");

    const normalized = normalizeCode(code);
    const salt = crypto.getRandomValues(new Uint8Array(16));
    const kek = await deriveKEKFromCode(normalized, salt, DEFAULT_KDF_PARAMS);

    const nonce = crypto.getRandomValues(new Uint8Array(12));
    const wrapped = await crypto.subtle.encrypt(
      { name: "AES-GCM", iv: nonce },
      kek,
      dek,
    );

    return {
      wrapped_dek: btoa(String.fromCharCode(...new Uint8Array(wrapped))),
      nonce: btoa(String.fromCharCode(...nonce)),
      kdf_salt: btoa(String.fromCharCode(...salt)),
      kdf_params: JSON.stringify(DEFAULT_KDF_PARAMS),
    };
  }, []);

  // ── exchangeCodeForPassword ───────────────────────────────────

  const exchangeCodeForPassword = useCallback(async (
    code: string,
    password: string,
    envelope: api.VaultKeyResponse,
  ): Promise<VaultEnvelope> => {
    const normalized = normalizeCode(code);
    const params = JSON.parse(envelope.kdf_params);

    const wrapped = Uint8Array.from(atob(envelope.wrapped_dek), (c) =>
      c.charCodeAt(0),
    );
    const nonce = Uint8Array.from(atob(envelope.nonce), (c) =>
      c.charCodeAt(0),
    );
    const salt = Uint8Array.from(atob(envelope.kdf_salt), (c) =>
      c.charCodeAt(0),
    );

    // Unwrap DEK with code-derived KEK
    const dek = await unwrapDEK(wrapped, nonce, normalized, salt, params);

    // Re-wrap under password-derived KEK
    const newEnvelope = await wrapDEK(dek, password);

    return {
      wrapped_dek: btoa(String.fromCharCode(...newEnvelope.wrapped)),
      nonce: btoa(String.fromCharCode(...newEnvelope.nonce)),
      kdf_salt: btoa(String.fromCharCode(...newEnvelope.kdfSalt)),
      kdf_params: JSON.stringify(newEnvelope.kdfParams),
    };
  }, []);

  // ── recovery key ─────────────────────────────────────────────

  const [recoveryEnabled, setRecoveryEnabled] = useState(false);

  const unlockWithRecoveryKey = useCallback(async (recoveryKey: string) => {
    const keyResp = await api.getVaultKey();
    if (!keyResp.recovery_enabled || !keyResp.recovery_wrapped_dek || !keyResp.recovery_nonce || !keyResp.recovery_kdf_salt || !keyResp.recovery_kdf_params) {
      throw new Error("Aucune clé de récupération n'est configurée pour ce coffre");
    }
    const wrapped = Uint8Array.from(atob(keyResp.recovery_wrapped_dek), (c) =>
      c.charCodeAt(0),
    );
    const nonce = Uint8Array.from(atob(keyResp.recovery_nonce), (c) =>
      c.charCodeAt(0),
    );
    const salt = Uint8Array.from(atob(keyResp.recovery_kdf_salt), (c) =>
      c.charCodeAt(0),
    );
    const params = JSON.parse(keyResp.recovery_kdf_params);

    const dek = await unwrapDEKWithRecoveryKey(wrapped, recoveryKey, salt, params, nonce);
    setSessionDEK(dek);
    markUnlocked();
    setDekVersion(keyResp.dek_version);
  }, []);

  const setRecoveryKey = useCallback(async (): Promise<string> => {
    const dek = getSessionDEK();
    if (!dek) throw new Error("Le coffre doit être déverrouillé pour générer une clé de récupération");

    const recoveryKey = generateRecoveryKey();
    const env = await wrapDEKWithRecoveryKey(dek, recoveryKey);
    await api.setVaultRecoveryKey({
      wrapped_dek: btoa(String.fromCharCode(...env.wrapped)),
      nonce: btoa(String.fromCharCode(...env.nonce)),
      kdf_salt: btoa(String.fromCharCode(...env.salt)),
      kdf_params: JSON.stringify(env.params),
    });
    setRecoveryEnabled(true);
    return recoveryKey;
  }, []);

  const revokeRecoveryKey = useCallback(async () => {
    await api.deleteVaultRecoveryKey();
    setRecoveryEnabled(false);
  }, []);

  const changePassword = useCallback(async (newPassword: string) => {
    const dek = getSessionDEK();
    if (!dek) throw new Error("Le coffre doit être déverrouillé pour changer le mot de passe");
    const envelope = await wrapDEK(dek, newPassword);
    await api.replaceVaultKey({
      wrapped_dek: btoa(String.fromCharCode(...envelope.wrapped)),
      nonce: btoa(String.fromCharCode(...envelope.nonce)),
      kdf_salt: btoa(String.fromCharCode(...envelope.kdfSalt)),
      kdf_params: JSON.stringify(envelope.kdfParams),
    });
    setDekVersion(1);
  }, []);

  // ── Context value ─────────────────────────────────────────────

  const value: VaultContextType = {
    status: computeCurrentStatus(),
    isUnlocked: isVaultUnlocked(),
    refreshStatus,
    unlock,
    lock,
    createVault,
    wrapForCode,
    exchangeCodeForPassword,
    dekVersion,
    recoveryEnabled,
    unlockWithRecoveryKey,
    setRecoveryKey,
    revokeRecoveryKey,
    changePassword,
  };

  return (
    <VaultContext.Provider value={value}>{children}</VaultContext.Provider>
  );
}

// ── Hook ───────────────────────────────────────────────────────────

export function useVault(): VaultContextType {
  const ctx = useContext(VaultContext);
  if (!ctx) throw new Error("useVault must be inside VaultProvider");
  return ctx;
}
