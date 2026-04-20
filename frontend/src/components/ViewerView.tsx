import { useEffect, useMemo, useState } from "react";
import {
  AnalyzeResponse,
  analyze,
  downloadBlob,
  exportMermaid,
  exportTableFormat,
  getCategories,
  getTargets,
  Category,
  Row,
} from "../api/client";
import AnnotationModal from "./AnnotationModal";
import MermaidPreview from "./MermaidPreview";

type Mode = "host" | "zone";
type Source = "exploded" | "grouped";

export default function ViewerView() {
  const [mode, setMode] = useState<Mode>("host");
  const [source, setSource] = useState<Source>("exploded");
  const [viewByZones, setViewByZones] = useState(false);
  const [filter, setFilter] = useState("");
  const [targets, setTargets] = useState<string[]>([]);
  const [groupedAvailable, setGroupedAvailable] = useState(true);
  const [target, setTarget] = useState("");
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [categories, setCategories] = useState<Category[]>([]);
  const [annotationFor, setAnnotationFor] = useState<string | null>(null);
  const [mermaidOpen, setMermaidOpen] = useState(false);
  const [mermaidFenced, setMermaidFenced] = useState(false);

  useEffect(() => {
    getCategories().then((r) => setCategories(r.categories)).catch(() => {});
  }, []);

  useEffect(() => {
    setError(null);
    getTargets(mode, source)
      .then((r) => {
        setTargets(r.targets);
        setGroupedAvailable(r.grouped_available);
        if (!r.targets.includes(target) && r.targets.length > 0) setTarget(r.targets[0]);
      })
      .catch((e) => {
        setError((e as Error).message);
        setTargets([]);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, source]);

  const filteredTargets = useMemo(() => {
    if (!filter.trim()) return targets;
    try {
      const rx = new RegExp(filter, "i");
      return targets.filter((t) => rx.test(t));
    } catch {
      return targets;
    }
  }, [filter, targets]);

  async function handleAnalyze() {
    if (!target) return;
    setError(null);
    try {
      const res = await analyze({
        target,
        target_is_zone: mode === "zone",
        view_by_zones: viewByZones,
        data_source: source,
      });
      setResult(res);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  function getTableData(): { headers: string[]; rows: string[][] } {
    if (!result) return { headers: [], rows: [] };
    const headers = result.columns;
    const rows = result.rows.map((r) => headers.map((h) => String(r[h] ?? "")));
    return { headers, rows };
  }

  async function handleExport(fmt: "mermaid" | "csv" | "yaml" | "excel", fullPolicies = false) {
    if (!result) return;
    try {
      if (fmt === "mermaid") {
        const blob = await exportMermaid({
          rows: result.rows,
          target,
          target_is_zone: mode === "zone",
          view_by_zones: viewByZones,
          fenced: mermaidFenced,
        });
        downloadBlob(blob, `attack_path_${safeName(target)}.md`);
        return;
      }
      const { headers, rows } = getTableData();
      const blob = await exportTableFormat(fmt, {
        headers,
        rows,
        target,
        view_by_zones: viewByZones,
        full_policies: fullPolicies,
      });
      const view = viewByZones ? "zones" : "hosts";
      const ext = fmt === "excel" ? "xlsx" : fmt;
      const suffix = fullPolicies ? "full_policies" : `${safeName(target)}_${view}`;
      downloadBlob(blob, `attack_path_${suffix}.${ext}`);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  const cellColorMap = useMemo(() => {
    const m: Record<string, string> = {};
    for (const c of categories) m[c.name] = c.color;
    return m;
  }, [categories]);

  return (
    <div>
      <div className="card">
        <h2>Attack Path Viewer</h2>

        <div className="toolbar">
          <label>
            Target:
            <input type="radio" checked={mode === "host"} onChange={() => setMode("host")} /> Host
            <input type="radio" checked={mode === "zone"} onChange={() => setMode("zone")} /> Zone
          </label>
          <label>
            Data:
            <input type="radio" checked={source === "exploded"} onChange={() => setSource("exploded")} /> Exploded
            <input
              type="radio"
              checked={source === "grouped"}
              disabled={!groupedAvailable}
              onChange={() => setSource("grouped")}
            />{" "}
            Grouped
          </label>
          <label>
            View:
            <input type="radio" checked={!viewByZones} onChange={() => setViewByZones(false)} /> Hosts
            <input type="radio" checked={viewByZones} onChange={() => setViewByZones(true)} /> Zones
          </label>
        </div>

        <div className="row">
          <label>Filter (regex):</label>
          <input
            type="text"
            className="grow"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            placeholder="optional regex to narrow the target list"
          />
          <select value={target} onChange={(e) => setTarget(e.target.value)} style={{ minWidth: 200 }}>
            {filteredTargets.map((t) => (
              <option key={t} value={t}>
                {t}
              </option>
            ))}
          </select>
          <button className="btn" onClick={handleAnalyze} disabled={!target}>
            Analyze
          </button>
        </div>
      </div>

      {error && (
        <div className="card" style={{ borderColor: "var(--negative)" }}>
          <strong style={{ color: "var(--negative)" }}>Error:</strong> {error}
        </div>
      )}

      {result && (
        <div className="card">
          <div className="toolbar">
            <span className="badge">
              {result.rows.length} row(s) for <strong>{target}</strong>
            </span>
            <button className="btn" onClick={() => setMermaidOpen(true)}>
              Mermaid Preview
            </button>
            <label>
              <input type="checkbox" checked={mermaidFenced} onChange={(e) => setMermaidFenced(e.target.checked)} />{" "}
              fenced code block
            </label>
            <button className="btn secondary" onClick={() => handleExport("mermaid")}>
              Export Mermaid
            </button>
            <button className="btn secondary" onClick={() => handleExport("csv")}>
              Export CSV
            </button>
            <button className="btn secondary" onClick={() => handleExport("yaml")}>
              Export YAML
            </button>
            <button className="btn secondary" onClick={() => handleExport("excel")}>
              Export Excel
            </button>
            <button className="btn secondary" onClick={() => handleExport("excel", true)}>
              Excel: Full Policies
            </button>
          </div>

          <div className="grid-wrap">
            <table className="grid">
              <thead>
                <tr>
                  {result.columns.map((c) => (
                    <th key={c}>{c}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {result.rows.map((r, i) => {
                  const cls = (r.classification as string) || "";
                  const tag = r.row_tag as string | null | undefined;
                  const bg = cls && cellColorMap[cls] ? cellColorMap[cls] : undefined;
                  const className = !bg && tag ? `row-${tag}` : "";
                  return (
                    <tr
                      key={i}
                      className={className}
                      style={bg ? { background: bg } : undefined}
                      onDoubleClick={() => {
                        if (result.mode !== "host") return;
                        const pol = (r.policy_name as string) || "";
                        const policies = pol.split("|").map((p) => p.trim()).filter(Boolean);
                        if (policies.length === 0) return;
                        if (policies.length === 1) {
                          setAnnotationFor(policies[0]);
                        } else {
                          const chosen = window.prompt(
                            `Row aggregates multiple policies. Which one to annotate?\n\n${policies.join("\n")}`,
                            policies[0],
                          );
                          if (chosen && policies.includes(chosen)) setAnnotationFor(chosen);
                        }
                      }}
                    >
                      {result.columns.map((c) => (
                        <td key={c}>{String(r[c] ?? "")}</td>
                      ))}
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
          {result.mode === "host" && (
            <p style={{ fontSize: "0.8rem", color: "var(--text-secondary)", marginTop: 8 }}>
              Double-click a row to annotate its policy.
            </p>
          )}
        </div>
      )}

      {annotationFor && (
        <AnnotationModal
          policyName={annotationFor}
          categories={categories}
          onClose={() => {
            setAnnotationFor(null);
            handleAnalyze();
          }}
        />
      )}

      {mermaidOpen && result && (
        <MermaidPreview
          rows={result.rows}
          target={target}
          targetIsZone={mode === "zone"}
          viewByZones={viewByZones}
          onClose={() => setMermaidOpen(false)}
        />
      )}
    </div>
  );
}

function safeName(s: string): string {
  return s.replace(/[^a-zA-Z0-9_-]/g, "_");
}
