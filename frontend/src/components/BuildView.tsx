import { useEffect, useState } from "react";
import { buildPipeline, pipelineStatus, PipelineResult } from "../api/client";

export default function BuildView() {
  const [file, setFile] = useState<File | null>(null);
  const [running, setRunning] = useState(false);
  const [result, setResult] = useState<PipelineResult | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [dbInfo, setDbInfo] = useState<{ exists: boolean; size: number } | null>(null);

  useEffect(() => {
    pipelineStatus()
      .then((s) => setDbInfo({ exists: s.db_exists, size: s.db_size_bytes }))
      .catch(() => setDbInfo({ exists: false, size: 0 }));
  }, [result]);

  async function handleRun() {
    if (!file) return;
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const res = await buildPipeline(file);
      setResult(res);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div>
      <div className="card">
        <h2>Build Attack Path Database</h2>
        <p style={{ color: "var(--text-secondary)" }}>
          Upload a PAN-OS <code>set</code>-command firewall config. The pipeline parses it into
          four tables and computes an attack-path matrix.
        </p>
        <div className="row">
          <input
            type="file"
            accept=".txt,.cfg,.conf,text/plain"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
          />
          <button className="btn" onClick={handleRun} disabled={!file || running}>
            {running ? "Building…" : "Build"}
          </button>
          {dbInfo && (
            <span className="badge">
              DB: {dbInfo.exists ? `${(dbInfo.size / 1024).toFixed(1)} KB` : "none"}
            </span>
          )}
        </div>
      </div>

      {error && (
        <div className="card" style={{ borderColor: "var(--negative)" }}>
          <strong style={{ color: "var(--negative)" }}>Error:</strong> {error}
        </div>
      )}

      {result && (
        <div className="card">
          <h3>Result</h3>
          <div className="row" style={{ marginBottom: 10 }}>
            {Object.entries(result.counts).map(([t, n]) => (
              <span key={t} className="badge">
                {t}: {n.toLocaleString()}
              </span>
            ))}
          </div>
          <details>
            <summary>Full log</summary>
            <pre className="log">{result.logs.join("\n")}</pre>
          </details>
        </div>
      )}
    </div>
  );
}
