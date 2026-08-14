import { useState, type FormEvent } from "react";
import { useVault } from "../hooks/useVault";
import { useT } from "../i18n/I18nContext";
import { WrongPasswordError } from "../lib/vault";

/**
 * Full-page overlay for vault unlock.
 *
 * Displayed when the organization has an active vault and the
 * user's DEK is not in memory (status === "locked").
 *
 * Password mode, plus recovery-key mode ("Mot de passe oublié ?") when
 * a recovery envelope is configured. After a recovery unlock, the user is
 * invited to set a new password (the DEK is re-wrapped client-side).
 */
export default function VaultUnlock() {
  const { t } = useT();
  const { unlock, unlockWithRecoveryKey, changePassword, recoveryEnabled } = useVault();

  const [mode, setMode] = useState<"password" | "recovery">("password");
  const [password, setPassword] = useState("");
  const [recoveryKey, setRecoveryKey] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [deriving, setDeriving] = useState(false);

  // Après déverrouillage via la clé de récupération → proposer un nouveau mdp
  const [recovered, setRecovered] = useState(false);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (mode === "password") {
      if (!password) return;
      setDeriving(true);
      try {
        await unlock(password);
      } catch (err: unknown) {
        setError(
          err instanceof WrongPasswordError
            ? t("vault.unlock_error")
            : (err as Error).message || t("vault.unlock_error"),
        );
      } finally {
        setDeriving(false);
      }
    } else {
      if (!recoveryKey) return;
      setDeriving(true);
      try {
        await unlockWithRecoveryKey(recoveryKey);
        setRecovered(true);
      } catch (err: unknown) {
        setError(
          err instanceof WrongPasswordError
            ? t("vault.recovery_error")
            : (err as Error).message || t("vault.recovery_error"),
        );
      } finally {
        setDeriving(false);
      }
    }
  }

  async function handleNewPassword(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!newPassword || newPassword.length < 6) {
      setError(t("vault.recovery_new_password_short"));
      return;
    }
    if (newPassword !== confirmPassword) {
      setError(t("vault.recovery_password_mismatch"));
      return;
    }
    setDeriving(true);
    try {
      await changePassword(newPassword);
      // Coffre déverrouillé + nouveau mdp en place → l'overlay disparaît
    } catch (err: unknown) {
      setError((err as Error).message || t("vault.unlock_error"));
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
          maxWidth: "440px",
          width: "100%",
          margin: "16px",
          background: "#fff",
        }}
      >
        {recovered ? (
          <>
            <h2>🔑 {t("vault.recovery_title")}</h2>
            <p style={{ color: "var(--gray-600)", marginBottom: 16 }}>
              {t("vault.recovery_change_password")}
            </p>

            <form onSubmit={handleNewPassword}>
              <div className="form-group">
                <label>{t("vault.recovery_new_password")}</label>
                <input
                  type="password"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  minLength={6}
                  disabled={deriving}
                />
              </div>
              <div className="form-group">
                <label>{t("vault.recovery_confirm_password")}</label>
                <input
                  type="password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  minLength={6}
                  disabled={deriving}
                />
              </div>

              {deriving && (
                <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12, color: "var(--gray-600)", fontSize: "0.85rem" }}>
                  <div className="spinner" />
                  <span>{t("vault.unlock_deriving")}</span>
                </div>
              )}

              <button
                type="submit"
                className="btn btn-primary"
                disabled={deriving || !newPassword || !confirmPassword}
              >
                {t("vault.recovery_set_password")}
              </button>
            </form>
          </>
        ) : (
          <>
            <h2>{t("vault.unlock_title")}</h2>
            <p style={{ color: "var(--gray-600)", marginBottom: 16 }}>
              {mode === "password"
                ? `${t("vault.unlock_title")} — ${t("vault.unlock_password")}`
                : t("vault.recovery_enter_key")}
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
              {mode === "password" ? (
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
              ) : (
                <div className="form-group">
                  <label>{t("vault.recovery_key_label")}</label>
                  <input
                    type="text"
                    value={recoveryKey}
                    onChange={(e) => setRecoveryKey(e.target.value.toUpperCase())}
                    placeholder="XXXX-XXXX-XXXX-XXXX"
                    required
                    autoFocus
                    disabled={deriving}
                    style={{ fontFamily: "monospace", letterSpacing: 1 }}
                  />
                </div>
              )}

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
                disabled={deriving || (mode === "password" ? !password : !recoveryKey)}
              >
                {deriving ? (
                  <div className="spinner" />
                ) : (
                  t("vault.unlock_submit")
                )}
              </button>
            </form>

            <div style={{ marginTop: 14, fontSize: "0.85rem" }}>
              {mode === "password" ? (
                recoveryEnabled ? (
                  <button
                    type="button"
                    className="btn"
                    style={{ background: "none", border: "none", color: "var(--blue)", cursor: "pointer", padding: 0 }}
                    onClick={() => { setMode("recovery"); setError(null); }}
                  >
                    {t("vault.recovery_forgot")}
                  </button>
                ) : (
                  <span style={{ color: "var(--gray-600)" }}>
                    {t("vault.recovery_not_configured")}
                  </span>
                )
              ) : (
                <button
                  type="button"
                  className="btn"
                  style={{ background: "none", border: "none", color: "var(--blue)", cursor: "pointer", padding: 0 }}
                  onClick={() => { setMode("password"); setError(null); }}
                >
                  {t("vault.recovery_back")}
                </button>
              )}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
