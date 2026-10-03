/** /settings — bring-your-own Genspark key + model choice (E-051).
 *
 *  The key lives in localStorage only and travels as a request header; the server uses it once and never
 *  stores, logs or echoes it. The deterministic verdict never depends on the model: it only proposes
 *  unmarked spans, reads images and picks an approved English translation. Catalog numbers come from the
 *  backend (/v1/models), which carries the measured values — nothing is typed here. */

import { useEffect, useState } from "react";
import { getByok, models, setByok, verifyKey, type Byok, type Lang, type ModelInfo, type VerifyResult } from "../api";
import { Icon } from "../brand";
import { useReveal } from "./hooks";
import { LiveBadge } from "./Shell";
import { numfmt, t } from "./strings";

export default function Settings({ lang }: { lang: Lang }) {
  useReveal();
  const nf = numfmt(lang);
  const saved = getByok();
  const [key, setKey] = useState(saved?.key ?? "");
  const [model, setModel] = useState(saved?.model ?? "");
  const [catalog, setCatalog] = useState<ModelInfo[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<VerifyResult | "error" | null>(null);
  const [flash, setFlash] = useState<"saved" | "cleared" | null>(null);
  const [show, setShow] = useState(false);

  useEffect(() => {
    let alive = true;
    models()
      .then((c) => {
        if (!alive) return;
        setCatalog(c.models);
        if (!model) setModel(c.default);
      })
      .catch(() => alive && setCatalog([]));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const current: Byok = { key: key.trim(), model };
  const canVerify = current.key.length >= 16 && !!model && !busy;

  async function onVerify() {
    setBusy(true);
    setResult(null);
    try {
      setResult(await verifyKey(current));
    } catch {
      setResult("error");
    } finally {
      setBusy(false);
    }
  }
  function onSave() {
    setByok(current);
    setFlash("saved");
  }
  function onClear() {
    setByok(null);
    setKey("");
    setResult(null);
    setFlash("cleared");
  }

  const active = getByok();
  const note = (m: ModelInfo) => (lang === "ar" ? m.note_ar : m.note_en);
  const tier = (m: ModelInfo) => t(lang, `set_tier_${m.tier}` as const);

  return (
    <main id="main" className="page">
      <header className="page-head">
        <div className="wrap">
          <p className="kicker">
            <LiveBadge lang={lang} /> BYOK · Genspark proxy
          </p>
          <h1>{t(lang, "set_title")}</h1>
          <p>{t(lang, "set_sub")}</p>
        </div>
      </header>

      <div className="wrap dev-grid">
        <section aria-labelledby="sk" data-reveal className="set-card">
          <h2 id="sk">{t(lang, "set_key_label")}</h2>
          <div className="set-field">
            <label htmlFor="byok-key">{t(lang, "set_key_label")}</label>
            <div className="set-input-row">
              <input
                id="byok-key"
                className="set-input"
                type={show ? "text" : "password"}
                autoComplete="off"
                spellCheck={false}
                dir="ltr"
                placeholder="gsk-…"
                value={key}
                onChange={(e) => {
                  setKey(e.target.value);
                  setResult(null);
                  setFlash(null);
                }}
              />
              <button type="button" className="btn-lux btn-lux--sm" onClick={() => setShow((v) => !v)} aria-pressed={show}>
                <Icon name={show ? "privacy-nostore" : "info"} size={18} />
              </button>
            </div>
            <p className="set-help">{t(lang, "set_key_help")}</p>
          </div>

          <div className="set-field">
            <label htmlFor="byok-model">{t(lang, "set_model_label")}</label>
            <select
              id="byok-model"
              className="set-input"
              value={model}
              onChange={(e) => {
                setModel(e.target.value);
                setResult(null);
                setFlash(null);
              }}
            >
              {(catalog ?? []).map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label} — {m.vendor} · {m.extract_exact}/{m.extract_total} · {nf.format(m.extract_p50_ms)} ms · {m.cost_x}×
                </option>
              ))}
            </select>
          </div>

          <div className="set-actions">
            <button type="button" className="btn-lux" disabled={!canVerify} onClick={onVerify}>
              <Icon name="shield-verify" size={20} />
              {busy ? t(lang, "set_verifying") : t(lang, "set_verify")}
            </button>
            <button type="button" className="btn-lux" disabled={!current.key || busy} onClick={onSave}>
              {t(lang, "set_save")}
            </button>
            {active && (
              <button type="button" className="btn-lux btn-lux--sm" onClick={onClear}>
                {t(lang, "set_clear")}
              </button>
            )}
          </div>

          <div className="set-status" role="status" aria-live="polite">
            {result && result !== "error" && result.ok && (
              <p className="set-ok">{t(lang, "set_ok", { model: result.model, ms: nf.format(result.latency_ms) })}</p>
            )}
            {result && result !== "error" && !result.ok && (
              <p className="set-fail">{t(lang, `set_fail_${result.reason}` as const)}</p>
            )}
            {result === "error" && <p className="set-fail">{t(lang, "set_fail_transport")}</p>}
            {flash === "saved" && <p className="set-ok">{t(lang, "set_saved")}</p>}
            {flash === "cleared" && <p>{t(lang, "set_cleared")}</p>}
            {active && !flash && (
              <p className="set-active">
                {t(lang, "set_active")}: <code dir="ltr">{active.model || "—"}</code>
              </p>
            )}
          </div>
          <p className="set-help">{t(lang, "set_note_rules")}</p>
        </section>

        <section aria-labelledby="sc" data-reveal>
          <h2 id="sc">{t(lang, "set_cat_title")}</h2>
          <p>{t(lang, "set_cat_sub")}</p>
          <div className="table-wrap" tabIndex={0} role="region" aria-labelledby="sc">
            <table className="ep-table set-table">
              <thead>
                <tr>
                  <th>{t(lang, "set_col_model")}</th>
                  <th>{t(lang, "set_col_tier")}</th>
                  <th>{t(lang, "set_col_cost")}</th>
                  <th>{t(lang, "set_col_exact")}</th>
                  <th>{t(lang, "set_col_speed")}</th>
                  <th>{t(lang, "set_col_ocr")}</th>
                  <th />
                </tr>
              </thead>
              <tbody>
                {(catalog ?? []).map((m) => (
                  <tr key={m.id} data-selected={m.id === model || undefined}>
                    <td>
                      <strong>{m.label}</strong> <span className="set-vendor">{m.vendor}</span>
                      {m.default && <span className="tag tag--live set-default">{t(lang, "set_default")}</span>}
                      <p className="set-note">{note(m)}</p>
                    </td>
                    <td>{tier(m)}</td>
                    <td dir="ltr">{m.cost_x}×</td>
                    <td dir="ltr">
                      {m.extract_exact}/{m.extract_total}
                    </td>
                    <td dir="ltr">{nf.format(m.extract_p50_ms)} ms</td>
                    <td>{m.ocr_ok ? t(lang, "set_ocr_yes") : t(lang, "set_ocr_no")}</td>
                    <td>
                      <button type="button" className="btn-lux btn-lux--sm" onClick={() => setModel(m.id)} aria-pressed={m.id === model}>
                        {t(lang, "set_use")}
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      </div>
    </main>
  );
}
