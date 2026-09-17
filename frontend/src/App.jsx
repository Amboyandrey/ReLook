import { useEffect, useState } from "react";
import { api } from "./api";
import DocumentList from "./components/DocumentList";
import DocumentViewer from "./components/DocumentViewer";
import ReviewPanel from "./components/ReviewPanel";
import "./App.css";

function loadReviewerName() {
  try {
    return localStorage.getItem("relook.reviewer") || "";
  } catch {
    return "";
  }
}

function saveReviewerName(name) {
  try {
    localStorage.setItem("relook.reviewer", name);
  } catch {
    // ignore -- private browsing / storage disabled
  }
}

export default function App() {
  const [status, setStatus] = useState("pending");
  const [documents, setDocuments] = useState([]);
  const [selectedId, setSelectedId] = useState(null);
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [categories, setCategories] = useState([]);
  const [reviewer, setReviewer] = useState(loadReviewerName);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    api.getTaxonomy().then((t) => setCategories(t.categories)).catch((e) => setError(e.message));
  }, []);

  async function refreshList(preserveSelection = true) {
    setLoading(true);
    try {
      const docs = await api.listDocuments({ status });
      setDocuments(docs);
      if (!preserveSelection || !docs.some((d) => d.id === selectedId)) {
        setSelectedId(docs[0]?.id ?? null);
      }
    } catch (e) {
      setError(e.message);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    refreshList(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [status]);

  useEffect(() => {
    if (selectedId == null) {
      setSelectedDoc(null);
      return;
    }
    api.getDocument(selectedId).then(setSelectedDoc).catch((e) => setError(e.message));
  }, [selectedId]);

  function handleReviewerChange(name) {
    setReviewer(name);
    saveReviewerName(name);
  }

  async function handleUpload(e) {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setError(null);
    try {
      await api.uploadDocument(file);
      await refreshList(false);
    } catch (err) {
      setError(`Upload failed: ${err.message}`);
    } finally {
      setUploading(false);
      e.target.value = "";
    }
  }

  function handleReviewSubmitted(updated) {
    setSelectedDoc(updated);
    // The document leaves the current tab once reviewed -- refresh the list
    // so it disappears from "pending" and shows up under its new status.
    refreshList(false);
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>ReLook — Review Queue</h1>
        <label className="upload-button">
          {uploading ? "Analyzing…" : "Upload document"}
          <input type="file" accept=".pdf,.docx,.txt,.md" onChange={handleUpload} disabled={uploading} hidden />
        </label>
      </header>

      {error && (
        <div className="error-banner" onClick={() => setError(null)}>
          {error} <span className="dismiss">(dismiss)</span>
        </div>
      )}

      <div className="app-body">
        <DocumentList
          documents={documents}
          status={status}
          onStatusChange={setStatus}
          selectedId={selectedId}
          onSelect={setSelectedId}
          loading={loading}
        />

        {selectedDoc ? (
          <>
            <DocumentViewer document={selectedDoc} />
            <ReviewPanel
              document={selectedDoc}
              categories={categories}
              reviewer={reviewer}
              onReviewerChange={handleReviewerChange}
              onSubmitted={handleReviewSubmitted}
              onError={setError}
            />
          </>
        ) : (
          <div className="empty-state">
            <p>Select a document, or upload one to get started.</p>
          </div>
        )}
      </div>
    </div>
  );
}
