import { useEffect, useState } from "react";
import { api } from "../api";

function emptyRequest() {
  return { text: "", deadline: "", owner: "", page: "" };
}

function toFormRequests(requests) {
  return requests.map((r) => ({
    text: r.text || "",
    deadline: r.deadline || "",
    owner: r.owner || "",
    page: r.page === null || r.page === undefined ? "" : String(r.page),
  }));
}

function toApiRequests(requests) {
  return requests
    .filter((r) => r.text.trim() !== "")
    .map((r) => ({
      text: r.text,
      deadline: r.deadline.trim() === "" ? null : r.deadline,
      owner: r.owner.trim() === "" ? null : r.owner,
      page: r.page.trim() === "" ? null : parseInt(r.page, 10),
    }));
}

export default function ReviewPanel({ document, categories, reviewer, onReviewerChange, onSubmitted, onError }) {
  const [category, setCategory] = useState(document.category);
  const [summary, setSummary] = useState(document.summary);
  const [requests, setRequests] = useState(toFormRequests(document.requests));
  const [needsHuman, setNeedsHuman] = useState(document.needs_human);
  const [reasonForReview, setReasonForReview] = useState(document.reason_for_review || "");
  const [notes, setNotes] = useState("");
  const [submitting, setSubmitting] = useState(false);

  // Reset local edit state whenever a different document is selected.
  useEffect(() => {
    setCategory(document.category);
    setSummary(document.summary);
    setRequests(toFormRequests(document.requests));
    setNeedsHuman(document.needs_human);
    setReasonForReview(document.reason_for_review || "");
    setNotes("");
  }, [document.id]);

  const isReviewed = document.status !== "pending";

  function updateRequest(index, field, value) {
    setRequests((prev) => prev.map((r, i) => (i === index ? { ...r, [field]: value } : r)));
  }

  function removeRequest(index) {
    setRequests((prev) => prev.filter((_, i) => i !== index));
  }

  async function submit(action) {
    if (!reviewer.trim()) {
      onError("Enter your name before approving or rejecting.");
      return;
    }
    setSubmitting(true);
    try {
      const payload = {
        action,
        reviewer: reviewer.trim(),
        notes: notes.trim() || null,
      };
      if (action === "approve") {
        Object.assign(payload, {
          category,
          summary,
          requests: toApiRequests(requests),
          entities: document.entities,
          needs_human: needsHuman,
          reason_for_review: reasonForReview.trim() || null,
        });
      }
      const updated = await api.submitReview(document.id, payload);
      onSubmitted(updated);
    } catch (e) {
      onError(e.message);
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="review-panel">
      <div className="review-header">
        <span className={`badge status-${document.status}`}>{document.status}</span>
        <span className="confidence-large">AI confidence: {Math.round(document.confidence * 100)}%</span>
        {document.auto_approve_eligible && <span className="badge eligible">auto-approve eligible</span>}
      </div>

      {document.reason_for_review && document.status === "pending" && (
        <p className="review-flag">⚑ {document.reason_for_review}</p>
      )}

      <label className="field">
        <span>Category</span>
        <select value={category} onChange={(e) => setCategory(e.target.value)} disabled={isReviewed}>
          {categories.map((c) => (
            <option key={c.name} value={c.name}>
              {c.name}
            </option>
          ))}
        </select>
      </label>

      <label className="field">
        <span>Summary</span>
        <textarea value={summary} onChange={(e) => setSummary(e.target.value)} disabled={isReviewed} rows={3} />
      </label>

      <div className="field">
        <span>Requests</span>
        {requests.map((r, i) => (
          <div className="request-row" key={i}>
            <input
              placeholder="What's being asked for"
              value={r.text}
              onChange={(e) => updateRequest(i, "text", e.target.value)}
              disabled={isReviewed}
            />
            <input
              placeholder="Deadline"
              value={r.deadline}
              onChange={(e) => updateRequest(i, "deadline", e.target.value)}
              disabled={isReviewed}
            />
            <input
              placeholder="Owner"
              value={r.owner}
              onChange={(e) => updateRequest(i, "owner", e.target.value)}
              disabled={isReviewed}
            />
            <input
              placeholder="Page"
              value={r.page}
              onChange={(e) => updateRequest(i, "page", e.target.value)}
              disabled={isReviewed}
            />
            {!isReviewed && (
              <button type="button" className="icon-button" onClick={() => removeRequest(i)}>
                ✕
              </button>
            )}
          </div>
        ))}
        {!isReviewed && (
          <button type="button" className="link-button" onClick={() => setRequests((prev) => [...prev, emptyRequest()])}>
            + add request
          </button>
        )}
      </div>

      <div className="field entities">
        <span>Entities (from AI, read-only)</span>
        <div className="entities-grid">
          <div>Person: {document.entities.person || "—"}</div>
          <div>Department: {document.entities.department || "—"}</div>
          <div>Dates: {document.entities.dates.length ? document.entities.dates.join(", ") : "—"}</div>
        </div>
      </div>

      <label className="field checkbox">
        <input type="checkbox" checked={needsHuman} onChange={(e) => setNeedsHuman(e.target.checked)} disabled={isReviewed} />
        <span>Needs human review</span>
      </label>

      {needsHuman && (
        <label className="field">
          <span>Reason for review</span>
          <input value={reasonForReview} onChange={(e) => setReasonForReview(e.target.value)} disabled={isReviewed} />
        </label>
      )}

      {!isReviewed && (
        <>
          <label className="field">
            <span>Your name</span>
            <input value={reviewer} onChange={(e) => onReviewerChange(e.target.value)} placeholder="reviewer name" />
          </label>

          <label className="field">
            <span>Notes (optional)</span>
            <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="e.g. reason for rejecting" />
          </label>

          <div className="actions">
            <button className="approve" disabled={submitting} onClick={() => submit("approve")}>
              Approve
            </button>
            <button className="reject" disabled={submitting} onClick={() => submit("reject")}>
              Reject
            </button>
          </div>
        </>
      )}

      {isReviewed && (
        <p className="muted">
          Reviewed by {document.reviewed_by} on {new Date(document.reviewed_at).toLocaleString()}
          {document.review_notes ? ` — "${document.review_notes}"` : ""}
        </p>
      )}
    </div>
  );
}
