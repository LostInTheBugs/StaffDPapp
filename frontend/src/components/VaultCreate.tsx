import { useState, type FormEvent } from "react";
import { useVault } from "../hooks/useVault";
import { useT } from "../i18n/I18nContext";

/**
 * Vault creation form — embedded in the organization settings page.
 *
 * Only renders for bureau members when vault is disabled.
 * Shows a mandatory warning checkbox before activation.
 */
export default function VaultCreate() {
  const { t } = useT();
  const { createVault } = useVault();
  const [password, setPassword] = useState("");
  const [confirmed, setConfirmed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (!password || !confirmed) return;

    setLoading(true);
    try {
      await createVault(password);
      setSuccess(true);
    } catch (err: unknown) {
      setError((err as Error).message);
    } finally {
      setLoading(false);
    }
  }

  if (success) {
    return (
      <div className="card mb-24" style={{ borderColor: "var(--green)" }}>
        <h2>{t("vault.title")}</h2>
        <div className="success-msg">
          ✅ {t("org.vault_active")}
        </div>
      </div>
    );
  }

  return (
    <div className="card mb-24">
      <h2>{t("vault.create_title")}</h2>

      {/* Warning — explicit, irreversible */}
      <div
        style={{
          background: "#fff3cd",
          border: "1px solid #ffc107",
          borderRadius: 8,
          padding: 12,
          marginBottom: 16,
          fontSize: "0.9rem",
        }}
      >
        <strong>{t("vault.create_warning")}</strong>
      </div>

      <form onSubmit={handleSubmit}>
        <div className="form-group">
          <label>{t("vault.create_password")}</label>
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            required
            minLength={6}
            disabled={loading}
            autoFocus
          />
        </div>

        {/* Mandatory acknowledgment checkbox */}
        <div
          style={{
            display: "flex",
            alignItems: "flex-start",
            gap: 8,
            marginBottom: 16,
          }}
        >
          <input
            type="checkbox"
            id="vault-confirm"
            checked={confirmed}
            onChange={(e) => setConfirmed(e.target.checked)}
            style={{ marginTop: 4, minWidth: 16 }}
          />
          <label
            htmlFor="vault-confirm"
            style={{
              fontSize: "0.85rem",
              color: "var(--gray-700)",
              cursor: "pointer",
              fontWeight: 400,
            }}
          >
            {t("vault.create_confirm_checkbox")}
          </label>
        </div>

        {error && <div className="error-msg">{error}</div>}

        <button
          type="submit"
          className="btn btn-primary"
          disabled={loading || !password || !confirmed}
          style={{ background: "var(--blue)" }}
        >
          {loading ? (
            <div className="spinner" />
          ) : (
            t("vault.create_submit")
          )}
        </button>
      </form>
    </div>
  );
}
