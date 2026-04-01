"use client";

import { useCallback, useRef, useState } from "react";
import { FileText, Upload, X } from "lucide-react";
import { toast } from "sonner";

const ACCEPTED_EXTENSIONS = [".txt", ".log", ".out", ".console"];
const MAX_FILE_SIZE = 20 * 1024 * 1024; // 20 MB

type LogUploadAreaProps = {
  uploadFile: File | null;
  setUploadFile: (file: File | null) => void;
  pasteText: string;
  setPasteText: (text: string) => void;
};

export function LogUploadArea({
  uploadFile,
  setUploadFile,
  pasteText,
  setPasteText,
}: LogUploadAreaProps) {
  const [dragOver, setDragOver] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const validateFile = (file: File): string | null => {
    const ext = file.name.substring(file.name.lastIndexOf(".")).toLowerCase();
    if (!ACCEPTED_EXTENSIONS.includes(ext))
      return `Unsupported file type "${ext}". Use ${ACCEPTED_EXTENSIONS.join(", ")}`;
    if (file.size > MAX_FILE_SIZE)
      return `File too large (${(file.size / 1024 / 1024).toFixed(1)} MB). Max is 20 MB.`;
    return null;
  };

  const handleFileSelect = useCallback(
    (file: File) => {
      const err = validateFile(file);
      if (err) { toast.error(err); return; }
      setUploadFile(file);
      setPasteText("");
    },
    [setUploadFile, setPasteText],
  );

  const onDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      setDragOver(false);
      const file = e.dataTransfer.files?.[0];
      if (file) handleFileSelect(file);
    },
    [handleFileSelect],
  );

  return (
    <>
      {/* Drop zone */}
      <div
        onDrop={onDrop}
        onDragOver={(e) => { e.preventDefault(); setDragOver(true); }}
        onDragLeave={() => setDragOver(false)}
        onClick={() => fileInputRef.current?.click()}
        className={`relative flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed p-8 text-center transition-colors cursor-pointer ${
          dragOver
            ? "border-hpe-green-500 bg-hpe-green-500/5"
            : "border-slate-300 bg-slate-50 hover:border-slate-400 dark:border-slate-600 dark:bg-slate-800/50 dark:hover:border-slate-500"
        }`}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".txt,.log,.out,.console"
          className="hidden"
          onChange={(e) => { const f = e.target.files?.[0]; if (f) handleFileSelect(f); }}
        />
        <div className="rounded-full bg-slate-200 p-3 dark:bg-slate-700">
          <Upload className="h-6 w-6 text-slate-500 dark:text-slate-400" />
        </div>
        <div>
          <p className="text-sm font-medium text-slate-700 dark:text-slate-200">
            Drag &amp; drop a build log file here
          </p>
          <p className="mt-1 text-xs text-slate-500 dark:text-slate-400">
            or click to browse · .txt, .log, .out, .console · max 20 MB
          </p>
        </div>
      </div>

      {/* Selected file indicator */}
      {uploadFile && (
        <div className="flex items-center gap-2 rounded-lg border border-hpe-green-500/30 bg-hpe-green-500/5 px-4 py-2.5">
          <FileText className="h-4 w-4 text-hpe-green-600" />
          <span className="flex-1 truncate text-sm font-medium text-slate-700 dark:text-slate-200">
            {uploadFile.name}
          </span>
          <span className="text-xs text-slate-500">
            {(uploadFile.size / 1024).toFixed(1)} KB
          </span>
          <button
            type="button"
            onClick={(e) => { e.stopPropagation(); setUploadFile(null); }}
            className="ml-1 rounded p-1 text-slate-400 hover:bg-slate-200 hover:text-slate-600 dark:hover:bg-slate-700"
          >
            <X className="h-3.5 w-3.5" />
          </button>
        </div>
      )}

      {/* Divider */}
      <div className="flex items-center gap-3">
        <div className="h-px flex-1 bg-slate-200 dark:bg-slate-700" />
        <span className="text-xs font-medium text-slate-400">OR PASTE LOG CONTENT</span>
        <div className="h-px flex-1 bg-slate-200 dark:bg-slate-700" />
      </div>

      {/* Paste area */}
      <textarea
        placeholder="Paste your Jenkins build log here…"
        value={pasteText}
        onChange={(e) => {
          setPasteText(e.target.value);
          if (e.target.value.trim()) setUploadFile(null);
        }}
        rows={5}
        className="w-full rounded-lg border border-slate-300 bg-white px-4 py-3 font-mono text-xs leading-relaxed text-slate-700 placeholder:text-slate-400 focus:border-hpe-green-500 focus:outline-none focus:ring-1 focus:ring-hpe-green-500 dark:border-slate-600 dark:bg-slate-800 dark:text-slate-200 dark:placeholder:text-slate-500"
      />
    </>
  );
}
