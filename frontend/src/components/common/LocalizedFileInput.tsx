import { useEffect, useId, useRef } from "react";

import { useLocale } from "../../i18n/locale";

type LocalizedFileInputProps = {
  accept?: string;
  required?: boolean;
  selectedFileName?: string | null;
  onFileChange: (file: File | null) => void;
};

function LocalizedFileInput({
  accept,
  required = false,
  selectedFileName,
  onFileChange,
}: LocalizedFileInputProps) {
  const inputId = useId();
  const inputRef = useRef<HTMLInputElement | null>(null);
  const { text } = useLocale();
  const hasSelection = Boolean(selectedFileName);

  useEffect(() => {
    if (!selectedFileName && inputRef.current) {
      inputRef.current.value = "";
    }
  }, [selectedFileName]);

  const handleOpenPicker = () => {
    inputRef.current?.click();
  };

  return (
    <div className="localized-file-input">
      <input
        ref={inputRef}
        id={inputId}
        className="localized-file-input-native"
        type="file"
        accept={accept}
        required={required}
        onChange={(event) => onFileChange(event.target.files?.[0] ?? null)}
      />

      <button
        type="button"
        className="localized-file-input-trigger"
        onClick={handleOpenPicker}
        aria-controls={inputId}
      >
        {hasSelection ? text.upload.changeFile : text.upload.chooseFile}
      </button>

      <span className={`localized-file-input-name${hasSelection ? " localized-file-input-name-selected" : ""}`}>
        {selectedFileName || text.upload.noFileSelected}
      </span>
    </div>
  );
}

export default LocalizedFileInput;
