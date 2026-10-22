import { useState } from "react";

interface Props {
  onFiles: (files: File[]) => void;
  hasFiles: boolean;
}

export function Dropzone({ onFiles, hasFiles }: Props) {
  const [over, setOver] = useState(false);

  return (
    <label
      className={`dropzone ${over ? "dropzone--over" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setOver(true);
      }}
      onDragLeave={() => setOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setOver(false);
        const files = Array.from(e.dataTransfer.files);
        if (files.length) onFiles(files);
      }}
    >
      <input
        type="file"
        multiple
        className="visually-hidden"
        aria-label="Choose files to share"
        onChange={(e) => {
          const files = Array.from(e.target.files ?? []);
          e.target.value = "";
          if (files.length) onFiles(files);
        }}
      />
      <span className="dropzone__main">
        {hasFiles ? "Drop more files to share them." : "Drop a file here to start sharing it."}
      </span>
      <span className="dropzone__hint">or click to choose files</span>
    </label>
  );
}
