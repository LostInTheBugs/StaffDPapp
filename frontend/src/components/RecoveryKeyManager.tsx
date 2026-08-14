import { useState } from "react";
import { useVault } from "../hooks/useVault";
import { useT } from "../i18n/I18nContext";

/**
 * Recovery-key management — shown in the organization settings when the
 * vault is active and unlocked (bureau members).
 *
 * The key is displayed EXACTLY ONCE after generation; the server only
 * stores the opaque envelope, so a lost key cannot be recovered.
 */
export default function RecoveryKeyManager() {
  const { t } = useT();
  const { recoveryEnabled, setRecoveryKey, revokeRecoveryKey } = useVault();

  const [newKey, setNewKey] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  async function handleGenerate() {
    setError(null);
    setMessage(null);
    setBusy(true);
    try {
      const key = await setRecoveryKey();
      setNewKey(key);
      setMessage(recoveryEnabled ? t("vault.recovery_replaced") : t("vault.recovery_created"));
    } catch (err: unknown) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  async function handleRevoke() {
    if (!window.confirm(t("vault.recovery_revoke_confirm"))) return;
    setError(null);
    setMessage(null);
    setBusy(true);
    try {
      await revokeRecoveryKey();
      setMessage(t("vault.recovery_revoked"));
    } catch (err: unknown) {
      setError((err as Error).message);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div style={{ marginTop: 14, borderTop: "1px solid var(--gray-200)", paddingTop: 14 }}>
      <p style={{ fontWeight: 600, marginBottom: 6 }}>
        🗝️ {t("vault.recovery_manager_title")}
      </p>
      <p style={{ fontSize: "0.85rem", color: "var(--gray-600)", marginBottom: 10 }}>
        {t("vault.recovery_manager_desc")}
      </p>

      {newKey && (
        <div
          style={{
            background: "#fff3cd",
            border: "1.5px dashed #b45309",
            borderRadius: 10,
            padding: 14,
            marginBottom: 12,
          }}
        >
          <p style={{ fontWeight: 700, marginBottom: 6 }}>
            🗝️ {t("vault.recovery_created_title")}
          </p>
          <div
            style={{
              fontFamily: "monospace",
              fontSize: "1.15rem",
              letterSpacing: 2,
              background: "#fff",
              border: "1px solid var(--gray-300)",
              borderRadius: 8,
              padding: "10px 14px",
              textAlign: "center",
              userSelect: "all",
              fontWeight: 700,
            }}
          >
            {newKey}
          </div>
          <p style={{ fontSize: "0.8rem", color: "var(--gray-600)", marginTop: 8 }}>
            {t("vault.recovery_created_never_again")}
          </p>
        </div>
      )}

      {message && <div className="success-msg" style={{ marginBottom: 8 }}>✅ {message}</div>}
      {error && <div className="error-msg" style={{ marginBottom: 8 }}>⚠️ {error}</div>}

      <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
        <button
          type="button"
          className="btn"
          style={{ padding: "6px 12px", fontSize: ".85rem" }}
          onClick={handleGenerate}
          disabled={busy}
        >
          {recoveryEnabled ? "🔄 " : "🔑 "}
          {recoveryEnabled ? t("vault.recovery_replace") : t("vault.recovery_generate")}
        </button>
        {recoveryEnabled && (
          <button
            type="button"
            className="btn"
            style={{ padding: "6px 12px", fontSize: ".85rem", background: "#fef2f2", color: "#b91c1c", border: "1px solid #fecaca" }}
            onClick={handleRevoke}
            disabled={busy}
          >
            🚫 {t("vault.recovery_revoke")}
          </button>
        )}
      </div>
    </div>
  );
}
