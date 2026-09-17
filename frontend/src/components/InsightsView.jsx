import { useEffect, useState } from "react";
import { api } from "../api";

function pct(x) {
  return x === null || x === undefined ? "—" : `${Math.round(x * 100)}%`;
}

export default function InsightsView({ onError }) {
  const [report, setReport] = useState(null);
  const [exporting, setExporting] = useState(false);
  const [exportResult, setExportResult] = useState(null);

  async function refresh() {
    try {
      setReport(await api.getAccuracyReport());
    } catch (e) {
      onError(e.message);
    }
  }

  useEffect(() => {
    refresh();
  }, []);

  async function handleExport() {
    setExporting(true);
    try {
      setExportResult(await api.exportCorrections());
    } catch (e) {
      onError(e.message);
    } finally {
      setExporting(false);
    }
  }

  if (!report) return <div className="insights-view"><p className="muted">Loading…</p></div>;

  const { needs_human_effectiveness: nh } = report;

  return (
    <div className="insights-view">
      <div className="insights-grid">
        <div className="stat-card">
          <div className="stat-value">{report.total_reviewed}</div>
          <div className="stat-label">Documents reviewed</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{report.by_action.approved}</div>
          <div className="stat-label">Approved</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{report.by_action.edited}</div>
          <div className="stat-label">Approved with edits</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{report.by_action.rejected}</div>
          <div className="stat-label">Rejected</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{pct(report.category_agreement_rate)}</div>
          <div className="stat-label">Category agreement</div>
        </div>
        <div className="stat-card">
          <div className="stat-value">{pct(nh.risky_miss_rate)}</div>
          <div className="stat-label">Risky-miss rate (needs_human=false)</div>
        </div>
      </div>

      <section className="insights-section">
        <h3>Accuracy by AI confidence</h3>
        {report.confidence_buckets.length === 0 ? (
          <p className="muted">Not enough reviewed documents yet.</p>
        ) : (
          <table className="tasks-table">
            <thead>
              <tr>
                <th>Confidence range</th>
                <th>Count</th>
                <th>Category agreement</th>
                <th>Risky-miss rate</th>
              </tr>
            </thead>
            <tbody>
              {report.confidence_buckets.map((b) => (
                <tr key={b.range}>
                  <td>{b.range}</td>
                  <td>{b.count}</td>
                  <td>{pct(b.category_agreement_rate)}</td>
                  <td>{pct(b.risky_miss_rate)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </section>

      <section className="insights-section">
        <h3>Auto-approve threshold</h3>
        <p>
          Current: <strong>{report.current_auto_approve_threshold}</strong> (from{" "}
          <code>config/taxonomy.yaml</code>)
        </p>
        <p>
          Recommended:{" "}
          <strong>
            {report.recommended_auto_approve_threshold ?? "not enough data yet"}
          </strong>
        </p>
        <p className="muted">{report.recommendation_basis}</p>
        {report.recommended_auto_approve_threshold !== null && (
          <p className="muted">
            To apply this, update <code>auto_approve_threshold</code> in{" "}
            <code>config/taxonomy.yaml</code> — this is a deliberate manual step, not
            applied automatically.
          </p>
        )}
      </section>

      <section className="insights-section">
        <h3>Correction dataset</h3>
        <p className="muted">
          Every reviewed document, pairing the AI's original output with what the human
          decided. Useful for prompt/few-shot tuning or a future automated eval.
        </p>
        <button className="link-button" onClick={handleExport} disabled={exporting}>
          {exporting ? "Exporting…" : "Export corrections.jsonl"}
        </button>
        {exportResult && (
          <p className="muted">
            Wrote {exportResult.count} rows to <code>{exportResult.path}</code>
          </p>
        )}
      </section>
    </div>
  );
}
