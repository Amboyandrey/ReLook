const STATUS_TABS = [
  { key: "pending", label: "Pending" },
  { key: "approved", label: "Approved" },
  { key: "rejected", label: "Rejected" },
];

export default function DocumentList({ documents, status, onStatusChange, selectedId, onSelect, loading }) {
  return (
    <div className="doc-list">
      <div className="doc-list-tabs">
        {STATUS_TABS.map((tab) => (
          <button
            key={tab.key}
            className={tab.key === status ? "tab active" : "tab"}
            onClick={() => onStatusChange(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {loading && <p className="muted">Loading...</p>}
      {!loading && documents.length === 0 && <p className="muted">No documents here.</p>}

      <ul className="doc-list-items">
        {documents.map((doc) => (
          <li
            key={doc.id}
            className={doc.id === selectedId ? "doc-item selected" : "doc-item"}
            onClick={() => onSelect(doc.id)}
          >
            <div className="doc-item-title">
              {doc.needs_human && <span className="flag" title="Needs human review">⚑</span>}
              {doc.filename}
            </div>
            <div className="doc-item-meta">
              <span className="badge">{doc.category}</span>
              <span className="confidence">{Math.round(doc.confidence * 100)}%</span>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
