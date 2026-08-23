"use client";

import { useCallback, useEffect, useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

type DocumentRecord = {
  id: string;
  original_filename: string;
  status: string;
  width: number;
  height: number;
  uploaded_at: string;
  originals_expire_at: string;
};

export default function Home() {
  const [documents, setDocuments] = useState<DocumentRecord[]>([]);
  const [message, setMessage] = useState<string>("");
  const [busy, setBusy] = useState(false);

  const refresh = useCallback(async () => {
    try {
      const response = await fetch(`${API_BASE}/documents`, { credentials: "include" });
      if (response.status === 401) {
        setMessage("Not signed in.");
        setDocuments([]);
        return;
      }
      setDocuments(await response.json());
      setMessage("");
    } catch {
      setMessage("API unreachable.");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  async function upload(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setMessage("");
    const form = new FormData(event.currentTarget);
    try {
      const response = await fetch(`${API_BASE}/documents`, {
        method: "POST",
        body: form,
        credentials: "include",
      });
      // The API returns a single fixed error shape; never render raw server text.
      setMessage(response.ok ? "Uploaded. Processing queued." : "Upload rejected.");
      if (response.ok) await refresh();
    } catch {
      setMessage("Upload failed.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <main>
      <h1>Amharic Document AI</h1>
      <p className="sub">
        Photograph an Ethiopian document; get structured Markdown and JSON back.
      </p>

      <div className="banner">
        <strong>Scaffold build.</strong> Layout analysis, line segmentation and
        recognition are explicit stubs — uploads are validated, stored and queued, but
        no text is recognised yet. Results are marked so placeholder output can never be
        mistaken for a transcription.
      </div>

      <form className="card" onSubmit={upload}>
        <label htmlFor="file">
          Document image
          <span className="hint">JPEG, PNG or WebP. Verified by content, not filename.</span>
        </label>
        <input id="file" type="file" name="file" accept="image/jpeg,image/png,image/webp" required />

        <label className="check">
          <input type="checkbox" name="research_opt_in" value="true" />
          <span>
            Allow this document to be used for research.
            <span className="hint">Separate from processing consent, and off by default.</span>
          </span>
        </label>

        <label className="check">
          <input type="checkbox" name="subject_is_minor" value="true" defaultChecked />
          <span>
            This document relates to a person under 18.
            <span className="hint">
              Checked by default. Documents relating to minors are excluded from every
              training set, enforced by the database.
            </span>
          </span>
        </label>

        <button type="submit" disabled={busy}>
          {busy ? "Uploading…" : "Upload"}
        </button>
        {message ? <p className="hint">{message}</p> : null}
      </form>

      <div className="card">
        <h2 style={{ fontSize: "1.05rem", margin: "0 0 .75rem" }}>Your documents</h2>
        {documents.length === 0 ? (
          <p className="hint">Nothing uploaded yet.</p>
        ) : (
          <table>
            <thead>
              <tr>
                <th>File</th>
                <th>Status</th>
                <th>Size</th>
                <th>Originals purged</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc) => (
                <tr key={doc.id}>
                  <td>{doc.original_filename}</td>
                  <td><code>{doc.status}</code></td>
                  <td>{doc.width}×{doc.height}</td>
                  <td>{new Date(doc.originals_expire_at).toLocaleDateString()}</td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </main>
  );
}
