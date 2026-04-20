import { useEffect, useState } from "react";
import { Category, getCategories, putCategories } from "../api/client";

export default function SettingsView() {
  const [categories, setCategories] = useState<Category[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    getCategories()
      .then((r) => setCategories(r.categories))
      .catch((e) => setError((e as Error).message))
      .finally(() => setLoading(false));
  }, []);

  function updateCat(i: number, patch: Partial<Category>) {
    setCategories((cs) => cs.map((c, j) => (j === i ? { ...c, ...patch } : c)));
    setSaved(false);
  }

  function removeCat(i: number) {
    setCategories((cs) => cs.filter((_, j) => j !== i));
    setSaved(false);
  }

  function addCat() {
    setCategories((cs) => [...cs, { name: "NEW CATEGORY", color: "#dddddd" }]);
    setSaved(false);
  }

  async function handleSave() {
    try {
      const r = await putCategories(categories);
      setCategories(r.categories);
      setSaved(true);
    } catch (e) {
      setError((e as Error).message);
    }
  }

  if (loading) return <div className="card">Loading…</div>;

  return (
    <div className="card">
      <h2>Annotation Categories</h2>
      <p style={{ color: "var(--text-secondary)" }}>
        Categories are used to classify firewall policies and colour matching rows in the viewer
        and Excel exports.
      </p>

      {error && <p style={{ color: "var(--negative)" }}>{error}</p>}

      <table className="grid" style={{ marginBottom: 12 }}>
        <thead>
          <tr>
            <th>Name</th>
            <th>Color</th>
            <th>Preview</th>
            <th />
          </tr>
        </thead>
        <tbody>
          {categories.map((c, i) => (
            <tr key={i}>
              <td>
                <input
                  type="text"
                  value={c.name}
                  onChange={(e) => updateCat(i, { name: e.target.value })}
                />
              </td>
              <td>
                <input
                  type="color"
                  value={c.color}
                  onChange={(e) => updateCat(i, { color: e.target.value })}
                />
                <input
                  type="text"
                  value={c.color}
                  onChange={(e) => updateCat(i, { color: e.target.value })}
                  style={{ marginLeft: 8, width: 90 }}
                />
              </td>
              <td style={{ background: c.color }}>&nbsp;</td>
              <td>
                <button className="btn danger" onClick={() => removeCat(i)}>
                  Remove
                </button>
              </td>
            </tr>
          ))}
        </tbody>
      </table>

      <div className="row">
        <button className="btn secondary" onClick={addCat}>
          Add category
        </button>
        <button className="btn" onClick={handleSave}>
          Save
        </button>
        {saved && <span className="badge" style={{ background: "#dcfce7" }}>Saved</span>}
      </div>
    </div>
  );
}
