import { useEffect, useState, type ReactNode } from "react";
import { fetchAdminConfig, fetchAdminCorpus } from "../../api/client";
import { FailureChips, StatePill, StatusBadge, shortHash } from "../../components/common";
import { useTree } from "../../context/TreeContext";
import type { AdminConfig, AdminCorpus, ClaimNodeData, ProofTreeResult } from "../../types";

/** Fetch once per key; failures are shown, never swallowed. */
function useFetched<T>(load: () => Promise<T>, key: string): { data: T | null; error: string | null } {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    let live = true;
    setData(null);
    setError(null);
    load()
      .then((d) => live && setData(d))
      .catch((e: Error) => live && setError(e.message));
    return () => {
      live = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key]);
  return { data, error };
}

const num = (n: number | null | undefined) => (n == null ? "â€“" : n.toFixed(2));

function Table({ head, children }: { head: string[]; children: ReactNode }) {
  return (
    <div className="tbl-wrap">
      <table className="tbl">
        <thead>
          <tr>{head.map((h) => <th key={h}>{h}</th>)}</tr>
        </thead>
        <tbody>{children}</tbody>
      </table>
    </div>
  );
}

function Kv({ rows }: { rows: [string, ReactNode][] }) {
  return (
    <dl className="kv">
      {rows.map(([k, v]) => (
        <div key={k}>
          <dt>{k}</dt>
          <dd>{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function Outcome({ value }: { value: string }) {
  const cls = value === "supports" || value === "challenge" || value === "challenges" ? "strong" : value === "not_usable" ? "bad" : "";
  return <span className={`outcome ${cls}`}>{value.replaceAll("_", " ")}</span>;
}

// ---------------------------------------------------------------- run summary
export function AdminOverview({ result }: { result: ProofTreeResult }) {
  const mock = result.llm_badge !== null;
  return (
    <div className="stack">
      <section className="panel">
        <h2>Run</h2>
        <Kv
          rows={[
            ["Scenario", result.title],
            ["Employee", `${result.employee.role} in ${result.employee.region}`],
            ["Case parameters", Object.entries(result.employee.params).map(([k, v]) => `${k} = ${String(v)}`).join(", ") || "none"],
            ["Model mode", mock ? <>{result.llm_badge}</> : result.llm_mode],
            ["Demo date", result.demo_date],
            ["Overall", <StatusBadge key="o" status={result.overall.status} />],
            ["Citation-only baseline", <StatusBadge key="b" status={result.baseline.status} />],
            ["Why", result.overall.reason],
          ]}
        />
      </section>

      <section className="panel">
        <h2>Claims</h2>
        <Table head={["Claim", "Text", "Status", "SE", "SC", "Failure type", "Missing input"]}>
          {result.claims.map((c) => (
            <tr key={c.id}>
              <td className="mono">{c.id}</td>
              <td>{c.text}</td>
              <td><StatusBadge status={c.status} /></td>
              <td className="n">{num(c.se)}</td>
              <td className="n">{num(c.sc)}</td>
              <td><FailureChips types={c.failure_types} /></td>
              <td>{c.missing_slots.join(", ") || "â€“"}</td>
            </tr>
          ))}
        </Table>
      </section>

      <section className="panel">
        <h2>Citation-only baseline checks</h2>
        <p className="note">The baseline only asks whether the cited passage exists and entails the claim. It applies no whitelist, freshness or scope filter.</p>
        <Table head={["Claim", "Cited passage", "Exists", "Entails", "NLI score"]}>
          {result.baseline.checks.map((b, i) => (
            <tr key={i}>
              <td className="mono">{b.claim_id}</td>
              <td className="mono">{b.passage_id}</td>
              <td>{b.exists ? "yes" : "no"}</td>
              <td>{b.entails ? "yes" : "no"}</td>
              <td className="n">{num(b.score)}{mock ? " (scripted)" : ""}</td>
            </tr>
          ))}
        </Table>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------- pipeline trace
export function TraceTab({ result }: { result: ProofTreeResult }) {
  const { data: cfg } = useFetched(fetchAdminConfig, "config");
  return (
    <div className="stack">
      {result.claims.map((c) => (
        <ClaimTraceView key={c.id} c={c} cfg={cfg} mock={result.llm_badge !== null} />
      ))}
    </div>
  );
}

function ClaimTraceView({ c, cfg, mock }: { c: ClaimNodeData; cfg: AdminConfig | null; mock: boolean }) {
  const t = c.trace;
  const th = cfg?.thresholds;
  const failedCond = c.conditions.some((x) => x.result === "fail");
  const missing = t.verify.missing_slots.length > 0;
  const fired =
    t.verify.sc >= (th?.refute_sc ?? 0.5) || failedCond
      ? 1
      : missing || t.verify.conflict
        ? 2
        : c.status === "Verified"
          ? 3
          : 4;
  return (
    <details className="panel claim-trace" open>
      <summary>
        <span className="mono">{c.id}</span> <StatusBadge status={c.status} /> <span className="claim-trace-text">{c.text}</span>
      </summary>

      <h3>1. Investigate</h3>
      <p className="note">Passages the answer cited, plus what retrieval adds. Only approved, hash-verified, fresh, applicable passages reach the model.</p>
      <Table head={["Passage", "Via", "State", "Retrieval", "NLI", "Outcome"]}>
        {t.investigate.map((x, i) => (
          <tr key={i}>
            <td className="mono">{x.passage_id}</td>
            <td>{x.via}</td>
            <td>{x.state ?? "not in corpus"}</td>
            <td className="n">{num(x.retrieval_score)}</td>
            <td>{x.nli_label ? `${x.nli_label} ${num(x.nli_score)}${mock ? " (scripted)" : ""}` : "not sent"}</td>
            <td><Outcome value={x.outcome} /></td>
          </tr>
        ))}
      </Table>
      {c.conditions.length > 0 && (
        <p className="note">
          Mandatory conditions of the best support: {c.conditions.map((x) => `${x.field} ${x.op} ${JSON.stringify(x.expected)} â†’ ${x.result}`).join("; ")}.
        </p>
      )}

      <h3>2. Challenge</h3>
      <p className="note">{t.challenge.length} counter-query templates run through the same retrieval.</p>
      {t.challenge.map((q, i) => (
        <div className="query" key={i}>
          <div className="query-head">
            <code>{q.template}</code>
            <span className="mono query-text">{q.query}</span>
          </div>
          {q.hits.length === 0 ? (
            <p className="note">No passages retrieved.</p>
          ) : (
            <Table head={["Passage", "Retrieval", "NLI", "Outcome"]}>
              {q.hits.map((h) => (
                <tr key={h.passage_id}>
                  <td className="mono">{h.passage_id}</td>
                  <td className="n">{num(h.retrieval_score)}</td>
                  <td>{h.nli_label ? `${h.nli_label} ${num(h.nli_score)}${mock ? " (scripted)" : ""}` : "judged earlier"}</td>
                  <td><Outcome value={h.outcome} /></td>
                </tr>
              ))}
            </Table>
          )}
        </div>
      ))}
      {c.evidence.filter((e) => e.role === "challenges").map((e) => (
        <p className="note" key={e.passage_id}>
          <strong className="mono">{e.passage_id}</strong>: {e.effect?.replaceAll("_", " ") ?? "unscored"}
          {e.trigger_conditions.length > 0 && ` Â· trigger ${e.trigger_conditions.map((x) => `${x.field} ${x.op} ${JSON.stringify(x.expected)} â†’ ${x.result}`).join(", ")}`}
        </p>
      ))}

      <h3>3. Verify</h3>
      <Kv
        rows={[
          ["SE (support)", num(t.verify.se)],
          ["SC (challenge)", num(t.verify.sc)],
          ["Equal-authority conflict", t.verify.conflict ? "yes" : "no"],
          ["Missing inputs", t.verify.missing_slots.join(", ") || "none"],
          ["Decision", <StatusBadge key="d" status={t.verify.status} />],
          ["Reason", t.verify.reason],
        ]}
      />
      <ol className="rules">
        <li className={fired === 1 ? "fired" : ""}>Refuted if SC â‰¥ {th?.refute_sc ?? 0.5} or a mandatory condition fails</li>
        <li className={fired === 2 ? "fired" : ""}>Unresolved if required inputs are missing or equal-authority sources conflict</li>
        <li className={fired === 3 ? "fired" : ""}>Verified if SE &gt; {th?.verify_se ?? 0.85}, SC &lt; {th?.verify_sc ?? 0.15} and all conditions pass</li>
        <li className={fired === 4 ? "fired" : ""}>Otherwise Unresolved</li>
      </ol>
    </details>
  );
}

// ---------------------------------------------------------------- corpus and whitelist
export function CorpusTab() {
  const { role, region, result } = useTree();
  const { data, error } = useFetched<AdminCorpus>(() => fetchAdminCorpus(role, region), `${role}/${region}`);
  const used = new Set(result?.roots.map((r) => r.id));
  if (error) return <p className="error">{error}</p>;
  if (!data) return <p className="empty">Loading the corpusâ€¦</p>;
  return (
    <div className="stack">
      <section className="panel">
        <h2>Approved sources</h2>
        <p className="note">Ingestion and retrieval reject any passage whose hub and path are not listed here.</p>
        <Table head={["Hub", "Approved paths"]}>
          {data.approved_sources.map((s) => (
            <tr key={s.hub}>
              <td className="mono">{s.hub}</td>
              <td className="mono">{s.paths.join("  ")}</td>
            </tr>
          ))}
        </Table>
      </section>

      <section className="panel">
        <h2>All passages, as seen by a {role} in {region}</h2>
        <p className="note">{data.passages.length} ingested. Highlighted rows appear in the current run.</p>
        <Table head={["Passage", "Title", "Version", "Effective", "Expires", "Doc status", "Region", "Roles", "Authority", "Source", "SHA-256", "State"]}>
          {data.passages.map((p) => (
            <tr key={p.passage_id} className={used.has(p.passage_id) ? "used" : ""}>
              <td className="mono nw">{p.passage_id}</td>
              <td>{p.title}</td>
              <td>{p.version}</td>
              <td className="mono nw">{p.effective_date}</td>
              <td className="mono nw">{p.expiry_date}</td>
              <td>{p.status}</td>
              <td>{p.region.join(", ")}</td>
              <td>{p.role_scope.join(", ")}</td>
              <td className="n">{p.authority}</td>
              <td className="mono">{p.source.hub}{p.source.path}</td>
              <td className="mono">{shortHash(p.hash)} {p.hash_ok ? "âœ”" : "âœ–"}</td>
              <td><StatePill state={p.state} label={p.state_label} /></td>
            </tr>
          ))}
        </Table>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------- matrix and settings
export function ConfigTab() {
  const { data, error } = useFetched(fetchAdminConfig, "config");
  if (error) return <p className="error">{error}</p>;
  if (!data) return <p className="empty">Loading settingsâ€¦</p>;
  const t = data.thresholds;
  return (
    <div className="stack">
      <section className="panel">
        <h2>Settings</h2>
        <Kv
          rows={[
            ["Model mode", data.llm_badge ?? data.llm_mode],
            ["Demo date (today)", data.demo_date],
            ["Data", data.data_label],
            ["Passages ingested", data.passage_count],
            ["Passages searchable", `${data.searchable_count} (approved and hash-verified)`],
          ]}
        />
      </section>

      <section className="panel">
        <h2>Verification matrix</h2>
        <p className="note">Plain Python, no model call. Rules are evaluated in this order for each claim.</p>
        <Table head={["Order", "Status", "Condition"]}>
          <tr><td className="n">1</td><td><StatusBadge status="Refuted" /></td><td>SC â‰¥ {t.refute_sc.toFixed(2)}, or a mandatory condition explicitly fails</td></tr>
          <tr><td className="n">2</td><td><StatusBadge status="Unresolved" /></td><td>Required intent slots are missing, or active sources of equal authority conflict</td></tr>
          <tr><td className="n">3</td><td><StatusBadge status="Verified" /></td><td>SE &gt; {t.verify_se.toFixed(2)} and SC &lt; {t.verify_sc.toFixed(2)} and all mandatory conditions met</td></tr>
          <tr><td className="n">4</td><td><StatusBadge status="Unresolved" /></td><td>Anything else, for example SE 0.90 with SC 0.30</td></tr>
        </Table>
        <p className="note">Overall answer: any Refuted claim makes it Refuted; otherwise any Unresolved claim makes it Unresolved; otherwise Verified.</p>
      </section>

      <section className="panel">
        <h2>Counter-query templates</h2>
        <p className="note">{"{c}"} is replaced with the claim text.</p>
        <ul className="templates">
          {data.counter_templates.map((tpl) => <li key={tpl}><code>{tpl}</code></li>)}
        </ul>
      </section>
    </div>
  );
}

// ---------------------------------------------------------------- raw payload
export function RawJsonTab({ result }: { result: ProofTreeResult }) {
  const [copyMsg, setCopyMsg] = useState<string | null>(null);
  const text = JSON.stringify(result, null, 2);
  const copy = async () => {
    try {
      await navigator.clipboard.writeText(text);
      setCopyMsg("Copied");
    } catch (e) {
      setCopyMsg(`Copy failed: ${(e as Error).message}`);
    }
  };
  return (
    <section className="panel">
      <div className="raw-head">
        <h2>Proof Tree payload</h2>
        <button className="ghost" onClick={copy}>Copy JSON</button>
        {copyMsg && <span className="note">{copyMsg}</span>}
      </div>
      <pre className="raw">{text}</pre>
    </section>
  );
}

