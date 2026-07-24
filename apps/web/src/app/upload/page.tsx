"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useApi } from "@/lib/api";
import type { Child, PresignResponse, Upload } from "@/lib/types";
import { ChildPicker } from "@/components/child-picker";

const STATUS_BADGE: Record<Upload["status"], string> = {
  pending: "bg-amber-100 text-amber-800",
  marked: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
};

export default function UploadPage() {
  const { request } = useApi();
  const [childrenList, setChildrenList] = useState<Child[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [uploads, setUploads] = useState<Upload[]>([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  useEffect(() => {
    request<Child[]>("/children")
      .then((kids) => {
        setChildrenList(kids);
        if (kids.length > 0) setSelectedId(kids[0].id);
      })
      .catch((e) => setMessage(String(e.message)));
  }, [request]);

  const refreshUploads = useCallback(
    (childId: string) => {
      request<Upload[]>(`/children/${childId}/uploads`)
        .then(setUploads)
        .catch((e) => setMessage(String(e.message)));
    },
    [request],
  );

  useEffect(() => {
    if (selectedId) refreshUploads(selectedId);
  }, [selectedId, refreshUploads]);

  async function onUpload() {
    const file = fileInput.current?.files?.[0];
    if (!file || !selectedId) return;
    setBusy(true);
    setMessage(null);
    try {
      // 1. Ask the API for a presigned PUT URL (creates the uploads row).
      const contentType = (
        ["image/jpeg", "image/png", "image/webp", "image/heic"].includes(file.type)
          ? file.type
          : "image/jpeg"
      ) as "image/jpeg";
      const presign = await request<PresignResponse>("/uploads/presign", {
        method: "POST",
        body: JSON.stringify({ child_id: selectedId, content_type: contentType }),
      });
      // 2. PUT the photo straight to S3 — it never touches our API.
      const putRes = await fetch(presign.url, {
        method: "PUT",
        headers: presign.headers,
        body: file,
      });
      if (!putRes.ok) throw new Error(`S3 upload failed (${putRes.status})`);
      setMessage("Uploaded! Marking usually lands within a minute — refresh below.");
      if (fileInput.current) fileInput.current.value = "";
      refreshUploads(selectedId);
    } catch (err) {
      setMessage(String((err as Error).message));
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-bold">Upload a photo of maths work</h1>
      <ChildPicker childrenList={childrenList} selectedId={selectedId} onSelect={setSelectedId} />

      <div className="space-y-3 rounded-xl border border-slate-200 bg-white p-4">
        <input
          ref={fileInput}
          type="file"
          accept="image/jpeg,image/png,image/webp,image/heic"
          capture="environment"
          className="block w-full text-sm"
        />
        <button
          onClick={onUpload}
          disabled={busy || !selectedId}
          className="rounded-lg bg-indigo-600 px-4 py-2 text-sm font-medium text-white disabled:opacity-50"
        >
          {busy ? "Uploading…" : "Upload"}
        </button>
        {message && <p className="text-sm text-slate-600">{message}</p>}
      </div>

      <section className="space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="font-semibold">Recent uploads</h2>
          <button
            onClick={() => selectedId && refreshUploads(selectedId)}
            className="text-sm text-indigo-600 hover:underline"
          >
            Refresh
          </button>
        </div>
        <ul className="space-y-2">
          {uploads.map((upload) => (
            <li
              key={upload.id}
              className="flex items-center justify-between rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm"
            >
              <span className="truncate pr-3 text-slate-500">
                {upload.s3_key.split("/").pop()}
              </span>
              <span className={`rounded-full px-2 py-0.5 text-xs ${STATUS_BADGE[upload.status]}`}>
                {upload.status}
              </span>
            </li>
          ))}
          {uploads.length === 0 && <li className="text-sm text-slate-500">No uploads yet.</li>}
        </ul>
      </section>
    </div>
  );
}
