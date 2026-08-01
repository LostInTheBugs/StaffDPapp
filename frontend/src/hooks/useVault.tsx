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
