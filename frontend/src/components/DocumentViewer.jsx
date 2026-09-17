import { api } from "../api";

export default function DocumentViewer({ document }) {
  const isPdf = document.content_type === "application/pdf";
  const fileUrl = api.fileUrl(document.id);

  return (
    <div className="doc-viewer">
      {isPdf ? (
        <iframe title={document.filename} src={fileUrl} className="pdf-frame" />
      ) : (
        <div className="text-preview">
          <div className="text-preview-header">
            {document.filename}
            <a href={fileUrl} download={document.filename} className="download-link">
              Download original
            </a>
          </div>
          <pre>{document.preview_text || "(no preview available)"}</pre>
        </div>
      )}
    </div>
  );
}
