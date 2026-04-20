import { useEffect, useRef, useState } from "react";
import { exportMermaid, Row, downloadBlob } from "../api/client";

declare global {
  interface Window {
    mermaid?: {
      initialize: (cfg: object) => void;
      render: (id: string, text: string) => Promise<{ svg: string }>;
    };
  }
}

interface Props {
  rows: Row[];
  target: string;
  targetIsZone: boolean;
  viewByZones: boolean;
  onClose: () => void;
}

export default function MermaidPreview({ rows, target, targetIsZone, viewByZones, onClose }: Props) {
  const viewportRef = useRef<HTMLDivElement>(null);
  const [error, setError] = useState<string | null>(null);
  const [chart, setChart] = useState<string>("");

  useEffect(() => {
    // Fetch the Mermaid source from the backend and render it client-side.
    exportMermaid({ rows, target, target_is_zone: targetIsZone, view_by_zones: viewByZones, fenced: false })
      .then((b) => b.text())
      .then((txt) => setChart(txt))
      .catch((e) => setError((e as Error).message));
  }, [rows, target, targetIsZone, viewByZones]);

  useEffect(() => {
    if (!chart || !viewportRef.current) return;
    let cancelled = false;

    (async () => {
      const start = Date.now();
      while (!window.mermaid) {
        if (Date.now() - start > 5000) {
          setError("Mermaid library failed to load from CDN — check network.");
          return;
        }
        await new Promise((r) => setTimeout(r, 100));
      }
      if (cancelled) return;

      try {
        window.mermaid.initialize({ startOnLoad: false, theme: "default", securityLevel: "loose" });
        const id = `m${Date.now()}`;
        const { svg } = await window.mermaid.render(id, chart);
        if (!cancelled && viewportRef.current) viewportRef.current.innerHTML = svg;
      } catch (e) {
        if (!cancelled) setError((e as Error).message);
      }
    })();

    return () => {
      cancelled = true;
    };
  }, [chart]);

  async function handleDownloadSvg() {
    if (!viewportRef.current) return;
    const svg = viewportRef.current.querySelector("svg");
    if (!svg) return;
    const blob = new Blob([svg.outerHTML], { type: "image/svg+xml" });
    downloadBlob(blob, `attack_path_${target.replace(/[^a-zA-Z0-9_-]/g, "_")}.svg`);
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" style={{ width: "90vw", maxWidth: 1200 }} onClick={(e) => e.stopPropagation()}>
        <h3>Mermaid Preview — {target}</h3>
        {error && <p style={{ color: "var(--negative)" }}>{error}</p>}
        <div ref={viewportRef} className="mermaid-viewport" />
        <div className="row" style={{ marginTop: 12 }}>
          <button className="btn secondary" onClick={handleDownloadSvg}>
            Download SVG
          </button>
          <span style={{ flex: 1 }} />
          <button className="btn" onClick={onClose}>
            Close
          </button>
        </div>
      </div>
    </div>
  );
}
