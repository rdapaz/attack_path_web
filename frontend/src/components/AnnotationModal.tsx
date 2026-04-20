import { useEffect, useState } from "react";
import { Category, deleteAnnotation, getAnnotation, putAnnotation } from "../api/client";

interface Props {
  policyName: string;
  categories: Category[];
  onClose: () => void;
}

export default function AnnotationModal({ policyName, categories, onClose }: Props) {
  const [classification, setClassification] = useState<string | null>(null);
  const [notes, setNotes] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getAnnotation(policyName)
      .then((a) => {
        setClassification(a.classification);
        setNotes(a.notes ?? "");
      })
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, [policyName]);

  async function handleSave() {
    try {
      await putAnnotation(policyName, { classification, notes: notes.trim() || null });
      onClose();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  async function handleClear() {
    try {
      await deleteAnnotation(policyName);
      onClose();
    } catch (e) {
      setError((e as Error).message);
    }
  }

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Annotate Policy</h3>
        <p>
          <strong>Policy:</strong> {policyName}
        </p>

        {loading && <p>Loading…</p>}

        {!loading && (
          <>
            <fieldset style={{ marginBottom: 12 }}>
              <legend>Classification</legend>
              <label style={{ display: "block" }}>
                <input
                  type="radio"
                  checked={classification === null}
                  onChange={() => setClassification(null)}
                />{" "}
                (none / clear)
              </label>
              {categories.map((c) => (
                <label key={c.name} style={{ display: "block" }}>
                  <input
                    type="radio"
                    checked={classification === c.name}
                    onChange={() => setClassification(c.name)}
                  />{" "}
                  <span className="swatch" style={{ background: c.color }} /> {c.name}
                </label>
              ))}
            </fieldset>

            <fieldset>
              <legend>Notes</legend>
              <textarea
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                placeholder="Additional context, remediation steps, ticket number…"
                style={{ width: "100%", minHeight: 100 }}
              />
            </fieldset>

            {error && <p style={{ color: "var(--negative)" }}>{error}</p>}

            <div className="row" style={{ marginTop: 12 }}>
              <button className="btn" onClick={handleSave}>
                Save
              </button>
              <button className="btn danger" onClick={handleClear}>
                Clear annotation
              </button>
              <span style={{ flex: 1 }} />
              <button className="btn secondary" onClick={onClose}>
                Cancel
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
