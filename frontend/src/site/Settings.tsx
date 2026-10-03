/** /settings — bring-your-own Genspark key + model choice (E-051).
 *
 *  One narrow column, three short blocks: key → model list → save. The model list is a compact radio
 *  list (3 recommended by default, "show all" expands); the selected row reveals its one-line measured
 *  note. Numbers come from /v1/models (measured, backend-owned) — nothing is typed here.
 *
 *  The key lives in localStorage only and travels as a request header; the server uses it once and never
 *  stores, logs or echoes it. The deterministic verdict never depends on the model. */

import { useEffect, useState } from "react";
import { getByok, models, setByok, verifyKey, type Byok, type Lang, type ModelInfo, type VerifyResult } from "../api";
import { Icon } from "../brand";
import { LiveBadge } from "./Shell";
import { numfmt, t } from "./strings";

const RECOMMENDED = 3;

export default function Settings({ lang }: { lang: Lang }) {
  const nf = numfmt(lang);
  const saved = getByok();
  const [key, setKey] = useState(saved?.key ?? "");
  const [model, setModel] = useState(saved?.model ?? "");
  const [catalog, setCatalog] = useState<ModelInfo[] | null>(null);
  const [all, setAll] = useState(false);
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
  const active = getByok();
  const list = catalog ?? [];
  const selectedIdx = list.findIndex((m) => m.id === model);
  const visible = all ? list : list.slice(0, Math.max(RECOMMENDED, selectedIdx + 1));
  const reset = () => {
    setResult(null);
    setFlash(null);
  };

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

  return (
    <main id="main" className="page">
      <header className="page-head">
        <div className="wrap set-wrap">
          <p className="kicker">
            <LiveBadge lang={lang} /> BYOK · Genspark
          </p>
          <h1>{t(lang, "set_title")}</h1>
          <p>{t(lang, "set_sub")}</p>
        </div>
      </header>

      <div className="wrap set-wrap set-stack">
        {/* 1 — key */}
        <section className="set-block" aria-labelledby="sk">
          <h2 id="sk">
            <span className="set-step">1</span> {t(lang, "set_key_label")}
          </h2>
          <div className="set-input-row">
            <input
              id="byok-key"
              className="set-input"
              type={show ? "text" : "password"}
              autoComplete="off"
              spellCheck={false}
              dir="ltr"
              placeholder="gsk-…"
              aria-label={t(lang, "set_key_label")}
              value={key}
              onChange={(e) => {
                setKey(e.target.value);
                reset();
              }}
            />
            <button type="button" className="set-icon-btn" onClick={() => setShow((v) => !v)} aria-pressed={show} aria-label={t(lang, "set_key_label")}>
              <Icon name={show ? "privacy-nostore" : "info"} size={18} />
            </button>
            <button type="button" className="btn-lux btn-lux--sm" disabled={!canVerify} onClick={onVerify}>
              {busy ? t(lang, "set_verifying") : t(lang, "set_verify")}
            </button>
          </div>
          <p className="set-help">{t(lang, "set_key_help")}</p>
          <div className="set-status" role="status" aria-live="polite">
            {result && result !== "error" && result.ok && (
              <p className="set-ok">{t(lang, "set_ok", { model: result.model, ms: nf.format(result.latency_ms) })}</p>
            )}
            {result && result !== "error" && !result.ok && <p className="set-fail">{t(lang, `set_fail_${result.reason}` as const)}</p>}
            {result === "error" && <p className="set-fail">{t(lang, "set_fail_transport")}</p>}
          </div>
        </section>

        {/* 2 — model list */}
        <section className="set-block" aria-labelledby="sm">
          <h2 id="sm">
            <span className="set-step">2</span> {t(lang, "set_model_label")}
          </h2>
          <p className="set-help">{t(lang, "set_cat_sub")}</p>
          <ul className="set-list" role="radiogroup" aria-labelledby="sm">
            {visible.map((m) => {
              const sel = m.id === model;
              return (
                <li key={m.id}>
                  <button
                    type="button"
                    role="radio"
                    aria-checked={sel}
                    className="set-row"
                    data-selected={sel || undefined}
                    onClick={() => {
                      setModel(m.id);
                      reset();
                    }}
                  >
                    <span className="set-radio" aria-hidden="true" />
                    <span className="set-row__main">
                      <span className="set-row__title">
                        <strong>{m.label}</strong>
                        <span className="set-vendor">{m.vendor}</span>
                        {m.default && <span className="tag tag--live">{t(lang, "set_default")}</span>}
                      </span>
                      <span className="set-row__stats" dir="ltr">
                        <span title={t(lang, "set_col_exact")}>
                          {m.extract_exact}/{m.extract_total}
                        </span>
                        <span title={t(lang, "set_col_speed")}>{nf.format(m.extract_p50_ms)} ms</span>
                        <span title={t(lang, "set_col_cost")}>{m.cost_x}×</span>
                        <span className="set-tier">{t(lang, `set_tier_${m.tier}` as const)}</span>
                      </span>
                      {sel && <span className="set-row__note">{lang === "ar" ? m.note_ar : m.note_en}</span>}
                    </span>
                  </button>
                </li>
              );
            })}
          </ul>
          {list.length > RECOMMENDED && (
            <button type="button" className="set-more" onClick={() => setAll((v) => !v)} aria-expanded={all}>
              <Icon name="chevron-down" size={16} />
              {all ? t(lang, "set_less") : t(lang, "set_more", { n: nf.format(list.length) })}
            </button>
          )}
        </section>

        {/* 3 — save */}
        <section className="set-block" aria-labelledby="ss">
          <h2 id="ss">
            <span className="set-step">3</span> {t(lang, "set_save")}
          </h2>
          <div className="set-actions">
            <button type="button" className="btn-lux" disabled={!current.key || busy} onClick={onSave}>
              <Icon name="shield-verify" size={20} />
              {t(lang, "set_save")}
            </button>
            {active && (
              <button type="button" className="btn-lux btn-lux--sm" onClick={onClear}>
                {t(lang, "set_clear")}
              </button>
            )}
          </div>
          <div className="set-status" role="status" aria-live="polite">
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
      </div>
    </main>
  );
}
