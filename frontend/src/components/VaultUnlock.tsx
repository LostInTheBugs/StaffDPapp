import { useState, type FormEvent } from "react";
import { useVault } from "../hooks/useVault";
import { useT } from "../i18n/I18nContext";
import { WrongPasswordError } from "../lib/vault";

/**
 * Full-page overlay for vault unlock.
 *
 * Displayed when the organization has an active vault and the
 * user's DEK is not in memory (status === "locked").
 */
export default function VaultUnlock() {
  const { t } = useT();
  const { unlock } = useVault();

  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [deriving, setDeriving] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!password) return;

    setDeriving(true);
    try {
      await unlock(password);
      // Success — the context status will update to "unlocked"
      // and the parent will re-render to hide this overlay
    } catch (err: unknown) {
      if (err instanceof WrongPasswordError) {
        setError(t("vault.unlock_error"));
      } else {
        setError((err as Error).message || t("vault.unlock_error"));
      }
    } finally {
      setDeriving(false);
    }
  }

  return (
    <div
      style={{
        position: "fixed",
        inset: 0,
        background: "rgba(0,0,0,0.6)",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        zIndex: 2000,
      }}
    >
      <div
        className="card"
        style={{
          maxWidth: "420px",
          width: "100%",
          margin: "16px",
          background: "#fff",
        }}
      >
        <h2>{t("vault.unlock_title")}</h2>
        <p style={{ color: "var(--gray-600)", marginBottom: 16 }}>
          {t("vault.unlock_title")} —{" "}
          {t("vault.unlock_password")}
        </p>

        {error && (
          <div
            style={{
              background: "#fff3cd",
              border: "1px solid #ffc107",
              borderRadius: 8,
              padding: 12,
              marginBottom: 12,
            }}
          >
            <p className="error-msg" style={{ marginBottom: 4 }}>
              {error}
            </p>
            <p style={{ fontSize: "0.85rem", color: "var(--gray-600)" }}>
              {t("vault.unlock_error_hint")}
            </p>
          </div>
        )}

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label>{t("vault.unlock_password")}</label>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              autoFocus
              disabled={deriving}
            />
          </div>

          {deriving && (
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: 8,
                marginBottom: 12,
                color: "var(--gray-600)",
                fontSize: "0.85rem",
              }}
            >
              <div className="spinner" />
              <span>{t("vault.unlock_deriving")}</span>
            </div>
          )}

          <button
            type="submit"
            className="btn btn-primary"
            disabled={deriving || !password}
          >
            {deriving ? (
              <div className="spinner" />
            ) : (
              t("vault.unlock_submit")
            )}
          </button>
        </form>
      </div>
    </div>
  );
}
