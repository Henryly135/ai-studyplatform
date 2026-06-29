import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, Navigate, useNavigate, useOutletContext, useParams } from "react-router-dom";

import ManagementPanel from "../../components/course-management/ManagementPanel";
import MaterialResourceCard from "../../components/course-management/MaterialResourceCard";
import LocalizedFileInput from "../../components/common/LocalizedFileInput";
import { useLocale } from "../../i18n/locale";
import {
  FaCheckCircle,
  FaClipboardList,
} from "react-icons/fa";
import { LuTrash2 } from "react-icons/lu";

import {
  abortMultipartManagedModuleMaterialUpload,
  abortMultipartManagedModuleMaterialUploadBestEffort,
  completeMultipartManagedModuleMaterialUpload,
  deleteManagedModule,
  deleteManagedModuleMaterial,
  getMultipartManagedModuleMaterialPartUploadUrl,
  initMultipartManagedModuleMaterialUpload,
  publishManagedModule,
  updateManagedModule,
  uploadManagedModuleMaterial,
  getQuizAuthoring,
  setModulePrerequisite,
  removeModulePrerequisite,
} from "../../services/course";
import type { QuizRecord } from "../../types/course";
import { emitAppRefresh } from "../../utils/refreshEvents";
import type { CourseManagementOutletContext } from "./CourseManagementLayout";

const MULTIPART_UPLOAD_THRESHOLD_BYTES = 100 * 1024 * 1024;
const MULTIPART_CHUNK_SIZE_BYTES = 10 * 1024 * 1024;

function getInitialEstimatedMinutes(durationLabel: string) {
  const match = durationLabel.match(/\d+/);
  return match ? match[0] : "";
}

function formatModuleStatusLabel(status: "available" | "locked" | "draft") {
  if (status === "available") {
    return "Published";
  }

  if (status === "locked") {
    return "Archived";
  }

  return "Draft";
}

function getModuleStatusPillClassName(status: "available" | "locked" | "draft") {
  if (status === "available") {
    return "course-management-status-pill-published";
  }

  if (status === "locked") {
    return "course-management-status-pill-archived";
  }

  return "course-management-status-pill-draft";
}

function moduleHasPublishableMaterial(materialCount: number) {
  return materialCount > 0;
}

function shouldUseMultipartUpload(file: File) {
  return file.size >= MULTIPART_UPLOAD_THRESHOLD_BYTES;
}

function inferMaterialType(file: File) {
  const normalizedMimeType = file.type.trim().toLowerCase();

  if (normalizedMimeType.startsWith("video/")) {
    return "video";
  }

  if (normalizedMimeType.startsWith("audio/")) {
    return "file";
  }

  if (normalizedMimeType.startsWith("image/")) {
    return "file";
  }

  if (normalizedMimeType === "application/pdf") {
    return "pdf";
  }

  if (
    normalizedMimeType.includes("word") ||
    normalizedMimeType === "application/msword" ||
    normalizedMimeType === "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
  ) {
    return "file";
  }

  if (
    normalizedMimeType.includes("presentation") ||
    normalizedMimeType === "application/vnd.ms-powerpoint" ||
    normalizedMimeType === "application/vnd.openxmlformats-officedocument.presentationml.presentation"
  ) {
    return "file";
  }

  if (
    normalizedMimeType.includes("spreadsheet") ||
    normalizedMimeType.includes("excel") ||
    normalizedMimeType === "text/csv"
  ) {
    return normalizedMimeType === "text/csv" ? "text" : "file";
  }

  if (
    normalizedMimeType.includes("zip") ||
    normalizedMimeType.includes("compressed") ||
    normalizedMimeType.includes("archive")
  ) {
    return "file";
  }

  if (normalizedMimeType.startsWith("text/")) {
    return "text";
  }

  const fileName = file.name.trim().toLowerCase();
  const extension = fileName.includes(".") ? fileName.split(".").pop() : "";

  if (!extension) {
    return "";
  }

  if (["mp4", "mov", "avi", "mkv", "webm", "m4v"].includes(extension)) {
    return "video";
  }

  if (["mp3", "wav", "aac", "m4a", "ogg", "flac"].includes(extension)) {
    return "file";
  }

  if (["jpg", "jpeg", "png", "gif", "webp", "svg"].includes(extension)) {
    return "file";
  }

  if (extension === "pdf") {
    return "pdf";
  }

  if (["doc", "docx"].includes(extension)) {
    return "file";
  }

  if (["ppt", "pptx"].includes(extension)) {
    return "file";
  }

  if (["xls", "xlsx", "csv"].includes(extension)) {
    return extension === "csv" ? "text" : "file";
  }

  if (["zip", "rar", "7z", "tar", "gz"].includes(extension)) {
    return "file";
  }

  if (["txt", "md"].includes(extension)) {
    return "text";
  }

  return extension;
}

function normalizeMultipartUploadUrl(uploadUrl: string) {
  if (typeof window === "undefined") {
    return uploadUrl;
  }

  try {
    const parsedUrl = new URL(uploadUrl);
    const currentOrigin = window.location.origin;
    const currentHost = window.location.host;

    if (parsedUrl.origin === currentOrigin || parsedUrl.host === currentHost) {
      return uploadUrl;
    }

    if (parsedUrl.pathname.startsWith("/learning-materials/")) {
      return `${currentOrigin}${parsedUrl.pathname}${parsedUrl.search}`;
    }

    return uploadUrl;
  } catch {
    return uploadUrl;
  }
}

async function uploadFileChunk(uploadUrl: string, chunk: Blob, contentType: string) {
  const response = await fetch(normalizeMultipartUploadUrl(uploadUrl), {
    method: "PUT",
    headers: contentType ? { "Content-Type": contentType } : undefined,
    body: chunk,
  });

  if (!response.ok) {
    throw new Error("Failed to upload one of the file chunks.");
  }

  const etag = response.headers.get("etag") ?? response.headers.get("ETag");
  if (!etag) {
    throw new Error("Multipart upload succeeded but the storage server did not return an ETag.");
  }

  return etag.replace(/^"(.*)"$/, "$1");
}

function CourseManagementModuleDetailPage() {
  const { moduleUuid } = useParams();
  const navigate = useNavigate();
  const { course, refreshCourse, managementSearchSuffix } = useOutletContext<CourseManagementOutletContext>();
  const { text } = useLocale();
  const module = useMemo(
    () => course.modules.find((item) => item.moduleUuid === moduleUuid) ?? null,
    [course.modules, moduleUuid]
  );

  const [title, setTitle] = useState(module?.title ?? "");
  const [description, setDescription] = useState(module?.summary ?? "");
  const [content, setContent] = useState(module?.content ?? "");
  const [estimatedMinutes, setEstimatedMinutes] = useState(module ? getInitialEstimatedMinutes(module.durationLabel) : "");
  const [isSavingModule, setIsSavingModule] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveSuccess, setSaveSuccess] = useState<string | null>(null);
  const [materialTitle, setMaterialTitle] = useState("");
  const [materialType, setMaterialType] = useState("");
  const [materialFile, setMaterialFile] = useState<File | null>(null);
  const [confirmPublishedUpload, setConfirmPublishedUpload] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);
  const [uploadStatus, setUploadStatus] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<number | null>(null);
  const [uploadToastSuccess, setUploadToastSuccess] = useState<string | null>(null);
  const [isPublishingModule, setIsPublishingModule] = useState(false);
  const [publishError, setPublishError] = useState<string | null>(null);
  const [publishSuccess, setPublishSuccess] = useState<string | null>(null);
  const [isDeletingModule, setIsDeletingModule] = useState(false);
  const [deleteModuleError, setDeleteModuleError] = useState<string | null>(null);
  const [deletingMaterialUuid, setDeletingMaterialUuid] = useState<string | null>(null);
  const [deleteMaterialError, setDeleteMaterialError] = useState<string | null>(null);
  const [quiz, setQuiz] = useState<QuizRecord | null | undefined>(undefined); // undefined = loading
  const [selectedPrerequisiteUuid, setSelectedPrerequisiteUuid] = useState(module?.prerequisiteModuleUuid ?? "");
  const [isSavingPrerequisite, setIsSavingPrerequisite] = useState(false);
  const [prerequisiteError, setPrerequisiteError] = useState<string | null>(null);
  const [prerequisiteSuccess, setPrerequisiteSuccess] = useState<string | null>(null);
  const activeMultipartUploadSessionRef = useRef<string | null>(null);
  const activeCourseUuidRef = useRef(course.courseUuid);
  const activeManagedModuleUuidRef = useRef<string | null>(null);
  const managedModuleUuid = module?.moduleUuid ?? null;

  activeCourseUuidRef.current = course.courseUuid;
  activeManagedModuleUuidRef.current = managedModuleUuid;

  const abortActiveUploadSession = useCallback(() => {
    const uploadSessionUuid = activeMultipartUploadSessionRef.current;
    const courseUuid = activeCourseUuidRef.current;
    const currentModuleUuid = activeManagedModuleUuidRef.current;
    if (!uploadSessionUuid || !currentModuleUuid) {
      return;
    }

    activeMultipartUploadSessionRef.current = null;
    abortMultipartManagedModuleMaterialUploadBestEffort(
      courseUuid,
      currentModuleUuid,
      uploadSessionUuid
    );
  }, []);

  useEffect(() => {
    if (!module) {
      return;
    }

    setTitle(module.title);
    setDescription(module.summary);
    setContent(module.content ?? "");
    setEstimatedMinutes(getInitialEstimatedMinutes(module.durationLabel));
    setConfirmPublishedUpload(false);
    setUploadStatus(null);
    setUploadProgress(null);
    setSelectedPrerequisiteUuid(module.prerequisiteModuleUuid ?? "");
  }, [module]);

  useEffect(() => {
    if (!uploadToastSuccess) {
      return;
    }

    const timer = window.setTimeout(() => {
      setUploadToastSuccess(null);
    }, 2400);

    return () => {
      window.clearTimeout(timer);
    };
  }, [uploadToastSuccess]);

  useEffect(() => {
    document.body.classList.add("course-management-body-lock");

    return () => {
      document.body.classList.remove("course-management-body-lock");
    };
  }, []);

  useEffect(() => {
    if (!module) return;
    let cancelled = false;
    getQuizAuthoring(course.courseUuid, module.moduleUuid)
      .then((result) => { if (!cancelled) setQuiz(result); })
      .catch(() => { if (!cancelled) setQuiz(null); });
    return () => { cancelled = true; };
  }, [course.courseUuid, module]);

  useEffect(() => {
    window.addEventListener("pagehide", abortActiveUploadSession);
    window.addEventListener("beforeunload", abortActiveUploadSession);

    return () => {
      window.removeEventListener("pagehide", abortActiveUploadSession);
      window.removeEventListener("beforeunload", abortActiveUploadSession);
      abortActiveUploadSession();
    };
  }, [abortActiveUploadSession]);

  if (!module) {
    return <Navigate to={`/course/${course.courseUuid}/management/modules${managementSearchSuffix}`} replace />;
  }

  const isPublishedModule = module.status === "available";
  const canPublishModule = moduleHasPublishableMaterial(module.materials.length);

  const handleModuleSave = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setIsSavingModule(true);
    setSaveError(null);
    setSaveSuccess(null);

    try {
      await updateManagedModule(course.courseUuid, module.moduleUuid, {
        title: title.trim(),
        description: description.trim(),
        content: content.trim(),
        estimatedMinutes: estimatedMinutes.trim() ? Number(estimatedMinutes) : null,
      });
      await refreshCourse();
      emitAppRefresh({ scope: "course:detail", courseUuid: course.courseUuid, moduleUuid: module.moduleUuid });
      setSaveSuccess("Module changes saved.");
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : "Failed to update module.");
    } finally {
      setIsSavingModule(false);
    }
  };

  const handleMaterialUpload = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!materialFile) {
      setUploadStatus(null);
      setUploadProgress(null);
      setUploadSuccess(null);
      setUploadError("Choose a file before uploading.");
      return;
    }

    if (isPublishedModule && !confirmPublishedUpload) {
      setUploadError("Please confirm that you understand this upload will be published immediately.");
      return;
    }

    setIsUploading(true);
    setUploadError(null);
    setUploadSuccess(null);
    setUploadStatus(null);
    setUploadProgress(0);

    try {
      if (shouldUseMultipartUpload(materialFile)) {
        const totalParts = Math.ceil(materialFile.size / MULTIPART_CHUNK_SIZE_BYTES);
        setUploadStatus(`Uploading large file in ${totalParts} parts...`);

        const uploadSession = await initMultipartManagedModuleMaterialUpload(course.courseUuid, module.moduleUuid, {
          title: materialTitle,
          materialType,
          fileName: materialFile.name,
          contentType: materialFile.type || "application/octet-stream",
          sizeBytes: materialFile.size,
        });
        activeMultipartUploadSessionRef.current = uploadSession.uploadSessionUuid;

        const completedParts: Array<{ partNumber: number; etag: string }> = [];

        try {
          for (let partIndex = 0; partIndex < totalParts; partIndex += 1) {
            const partNumber = partIndex + 1;
            const start = partIndex * MULTIPART_CHUNK_SIZE_BYTES;
            const end = Math.min(start + MULTIPART_CHUNK_SIZE_BYTES, materialFile.size);
            const chunk = materialFile.slice(start, end);
            const partUrl = await getMultipartManagedModuleMaterialPartUploadUrl(
              course.courseUuid,
              module.moduleUuid,
              uploadSession.uploadSessionUuid,
              partNumber
            );

            setUploadStatus(`Uploading part ${partNumber} of ${totalParts}...`);
            const etag = await uploadFileChunk(partUrl.uploadUrl, chunk, materialFile.type || "application/octet-stream");
            completedParts.push({ partNumber, etag });
            setUploadProgress(Math.round((partNumber / totalParts) * 100));
          }

          setUploadStatus("Finalizing upload...");
          setUploadProgress(95);
          await completeMultipartManagedModuleMaterialUpload(
            course.courseUuid,
            module.moduleUuid,
            uploadSession.uploadSessionUuid,
            completedParts
          );
          activeMultipartUploadSessionRef.current = null;
          setUploadProgress(100);
        } catch (error) {
          try {
            await abortMultipartManagedModuleMaterialUpload(
              course.courseUuid,
              module.moduleUuid,
              uploadSession.uploadSessionUuid
            );
          } catch {
            // Best-effort cleanup. The original upload error is more useful to surface.
          } finally {
            activeMultipartUploadSessionRef.current = null;
          }

          throw error;
        }
      } else {
        setUploadStatus("Uploading file...");
        setUploadProgress(35);
        await uploadManagedModuleMaterial(course.courseUuid, module.moduleUuid, {
          title: materialTitle,
          materialType,
          file: materialFile,
        });
        setUploadProgress(100);
      }

      await refreshCourse();
      emitAppRefresh({ scope: "course:materials", courseUuid: course.courseUuid, moduleUuid: module.moduleUuid });
      emitAppRefresh({ scope: "course:detail", courseUuid: course.courseUuid, moduleUuid: module.moduleUuid });
      setMaterialTitle("");
      setMaterialType("");
      setMaterialFile(null);
      setConfirmPublishedUpload(false);
      setUploadStatus(null);
      activeMultipartUploadSessionRef.current = null;
      setUploadSuccess("Material uploaded successfully.");
      setUploadToastSuccess("Material uploaded successfully.");
    } catch (error) {
      setUploadStatus(null);
      setUploadProgress(null);
      setUploadError(error instanceof Error ? error.message : "Failed to upload material.");
    } finally {
      setIsUploading(false);
    }
  };

  const handleModulePublish = async () => {
    if (!canPublishModule) {
      setPublishError("Upload at least one material before publishing this module.");
      setPublishSuccess(null);
      return;
    }

    setIsPublishingModule(true);
    setPublishError(null);
    setPublishSuccess(null);

    try {
      await publishManagedModule(course.courseUuid, module.moduleUuid);
      await refreshCourse();
      emitAppRefresh({ scope: "course:managed", courseUuid: course.courseUuid, moduleUuid: module.moduleUuid });
      emitAppRefresh({ scope: "course:catalog", courseUuid: course.courseUuid, moduleUuid: module.moduleUuid });
      emitAppRefresh({ scope: "course:detail", courseUuid: course.courseUuid, moduleUuid: module.moduleUuid });
      setPublishSuccess("Module published successfully.");
      setUploadToastSuccess("Module published successfully.");
    } catch (error) {
      setPublishError(error instanceof Error ? error.message : "Failed to publish module.");
    } finally {
      setIsPublishingModule(false);
    }
  };

  const handleModuleDelete = async () => {
    const confirmed = window.confirm(
      `Delete "${module.title}"? This will permanently remove the module and its materials.`
    );
    if (!confirmed || isDeletingModule) {
      return;
    }

    setIsDeletingModule(true);
    setDeleteModuleError(null);

    try {
      await deleteManagedModule(course.courseUuid, module.moduleUuid);
      await refreshCourse();
      navigate(`/course/${course.courseUuid}/management/modules${managementSearchSuffix}`, { replace: true });
    } catch (error) {
      setDeleteModuleError(error instanceof Error ? error.message : "Failed to delete module.");
    } finally {
      setIsDeletingModule(false);
    }
  };

  const handleMaterialDelete = async (materialUuid: string, materialTitle: string) => {
    const confirmed = window.confirm(`Delete "${materialTitle}"? This will remove the material file and record.`);
    if (!confirmed || deletingMaterialUuid) {
      return;
    }

    setDeletingMaterialUuid(materialUuid);
    setDeleteMaterialError(null);

    try {
      await deleteManagedModuleMaterial(course.courseUuid, module.moduleUuid, materialUuid);
      await refreshCourse();
      emitAppRefresh({ scope: "course:materials", courseUuid: course.courseUuid, moduleUuid: module.moduleUuid });
      emitAppRefresh({ scope: "course:detail", courseUuid: course.courseUuid, moduleUuid: module.moduleUuid });
    } catch (error) {
      setDeleteMaterialError(error instanceof Error ? error.message : "Failed to delete material.");
    } finally {
      setDeletingMaterialUuid(null);
    }
  };

  const eligiblePrerequisiteModules = course.modules.filter(
    (m) => (m.sortOrder ?? 0) < (module.sortOrder ?? 0)
  );

  const handlePrerequisiteSave = async () => {
    setIsSavingPrerequisite(true);
    setPrerequisiteError(null);
    setPrerequisiteSuccess(null);

    try {
      if (selectedPrerequisiteUuid) {
        await setModulePrerequisite(course.courseUuid, module.moduleUuid, selectedPrerequisiteUuid);
      } else {
        await removeModulePrerequisite(course.courseUuid, module.moduleUuid);
      }
      await refreshCourse();
      setPrerequisiteSuccess("Prerequisite updated.");
    } catch (error) {
      setPrerequisiteError(error instanceof Error ? error.message : "Failed to update prerequisite.");
    } finally {
      setIsSavingPrerequisite(false);
    }
  };

  return (
    <section className="course-management-page course-management-page-module-detail">
      {uploadToastSuccess ? (
        <div className="course-management-toast course-management-toast-success" role="status" aria-live="polite">
          <strong>Upload complete</strong>
          <span>{uploadToastSuccess}</span>
        </div>
      ) : null}

      <Link to={`/course/${course.courseUuid}/management/modules${managementSearchSuffix}`} className="course-management-back-link">
        Back to modules
      </Link>

      <div className="course-management-section-heading">
        <div>
          <span className="course-surface-badge">Module Detail</span>
          <div className="course-management-title-row">
            <h1>{module.title}</h1>
            <span className={`course-management-status-pill ${getModuleStatusPillClassName(module.status)}`}>
              {formatModuleStatusLabel(module.status)}
            </span>
            {!isPublishedModule ? (
              <span
                className="course-management-tooltip-wrapper"
                title={canPublishModule ? "Publish this module now." : "Upload at least one material before publishing this module."}
              >
                <button
                  type="button"
                  className="course-management-action-button course-management-action-button-primary"
                  onClick={handleModulePublish}
                  disabled={isPublishingModule || !canPublishModule}
                >
                  {isPublishingModule ? "Publishing..." : "Publish module"}
                </button>
              </span>
            ) : null}
            <button
              type="button"
              className="course-management-action-button course-management-action-button-danger"
              onClick={handleModuleDelete}
              disabled={isDeletingModule}
            >
              {isDeletingModule ? "Deleting..." : "Delete module"}
            </button>
          </div>
          <p>Edit module content, refine teaching notes, and upload new materials for this module.</p>
          {publishError ? (
            <div className="course-management-inline-alert">
              <strong>Unable to publish module.</strong>
              <span>{publishError}</span>
            </div>
          ) : null}
          {publishSuccess ? <p className="course-management-inline-success">{publishSuccess}</p> : null}
          {deleteModuleError ? (
            <div className="course-management-inline-alert">
              <strong>Unable to delete module.</strong>
              <span>{deleteModuleError}</span>
            </div>
          ) : null}
        </div>
      </div>

      <div className="course-management-grid">
        <ManagementPanel title="Module content">
          <form className="course-management-form course-management-form-single" onSubmit={handleModuleSave}>
            <label className="course-management-field course-management-field-full">
              <span>Title</span>
              <input value={title} onChange={(event) => setTitle(event.target.value)} required />
            </label>

            <label className="course-management-field course-management-field-full">
              <span>Description</span>
              <textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={4} />
            </label>

            <label className="course-management-field course-management-field-full">
              <span>Content</span>
              <textarea value={content} onChange={(event) => setContent(event.target.value)} rows={8} />
            </label>

            <label className="course-management-field">
              <span>Estimated minutes</span>
              <input
                type="number"
                min="1"
                value={estimatedMinutes}
                onChange={(event) => setEstimatedMinutes(event.target.value)}
              />
            </label>

            {saveError ? (
              <div className="course-management-inline-alert course-management-field-full">
                <strong>Unable to update module.</strong>
                <span>{saveError}</span>
              </div>
            ) : null}
            {saveSuccess ? <p className="course-management-inline-success">{saveSuccess}</p> : null}

            <div className="course-management-form-actions course-management-field-full">
              <button
                type="submit"
                className="course-management-action-button course-management-action-button-primary"
                disabled={isSavingModule}
              >
                {isSavingModule ? "Saving..." : "Update module"}
              </button>
            </div>
          </form>
        </ManagementPanel>

        <ManagementPanel title="Upload material">
          <form className="course-management-form course-management-form-single" onSubmit={handleMaterialUpload}>
            <div className="course-management-inline-note course-management-field-full">
              <strong>Upload order</strong>
              <span>New material will be added to the end of this module's material list.</span>
            </div>

            {isPublishedModule ? (
              <div className="course-management-inline-warning course-management-field-full">
                <strong>Published module notice</strong>
                <span>
                  This module is already published. Any new material uploaded here will become published immediately after
                  upload.
                </span>
              </div>
            ) : null}

            <label className="course-management-field course-management-field-full">
              <span>Material title</span>
              <input value={materialTitle} onChange={(event) => setMaterialTitle(event.target.value)} />
            </label>

            <label className="course-management-field">
              <span>Material type</span>
              <input value={materialType} onChange={(event) => setMaterialType(event.target.value)} />
            </label>

            <label className="course-management-field course-management-field-full">
              <span>{text.upload.materialFileLabel}</span>
              <LocalizedFileInput
                selectedFileName={materialFile?.name ?? null}
                onFileChange={(file) => {
                  setMaterialFile(file);
                  setUploadError(null);
                  setMaterialType(file ? inferMaterialType(file) : "");
                }}
              />
            </label>

            {isPublishedModule ? (
              <label className="course-management-checkbox course-management-field-full">
                <input
                  type="checkbox"
                  checked={confirmPublishedUpload}
                  onChange={(event) => setConfirmPublishedUpload(event.target.checked)}
                />
                <span>I understand this material will be published immediately after upload.</span>
              </label>
            ) : null}

            {uploadError ? (
              <div className="course-management-inline-alert course-management-field-full">
                <strong>Unable to upload material.</strong>
                <span>{uploadError}</span>
              </div>
            ) : null}
            {isUploading && uploadProgress !== null ? (
              <div className="course-management-upload-progress course-management-field-full" aria-live="polite">
                <div className="course-management-upload-progress-track">
                  <div
                    className="course-management-upload-progress-fill"
                    style={{ width: `${Math.max(0, Math.min(uploadProgress, 100))}%` }}
                  />
                </div>
                <div className="course-management-upload-progress-meta">
                  <span>{uploadStatus || "Uploading..."}</span>
                  <strong>{uploadProgress}%</strong>
                </div>
              </div>
            ) : null}
            {uploadStatus && !isUploading ? <p className="course-management-inline-status">{uploadStatus}</p> : null}
            {uploadSuccess ? <p className="course-management-inline-success">{uploadSuccess}</p> : null}

            <div className="course-management-form-actions course-management-field-full">
              <button
                type="submit"
                className="course-management-action-button course-management-action-button-primary"
                disabled={isUploading || (isPublishedModule && !confirmPublishedUpload)}
              >
                {isUploading ? "Uploading..." : "Upload material"}
              </button>
            </div>
          </form>
        </ManagementPanel>
      </div>

      <ManagementPanel title="Current materials" style={{ marginBottom: "1.25rem" }}>
        {deleteMaterialError ? (
          <div className="course-management-inline-alert" style={{ marginBottom: "1rem" }}>
            <strong>Unable to delete material.</strong>
            <span>{deleteMaterialError}</span>
          </div>
        ) : null}
        <div className="course-management-material-grid">
          {module.materials.map((material) => (
            <div key={material.materialUuid} className="course-management-material-card-with-actions">
              <button
                type="button"
                className="course-management-material-delete-icon"
                onClick={() => void handleMaterialDelete(material.materialUuid, material.title)}
                disabled={deletingMaterialUuid === material.materialUuid}
                aria-label={deletingMaterialUuid === material.materialUuid ? "Deleting material" : `Delete ${material.title}`}
                title={deletingMaterialUuid === material.materialUuid ? "Deleting..." : "Delete material"}
              >
                <LuTrash2 size={18} aria-hidden="true" />
              </button>
              <MaterialResourceCard material={material} />
            </div>
          ))}

          {module.materials.length === 0 && (
            <div className="course-empty-state">
              <strong>No materials yet</strong>
              <p>Upload a file using the form above.</p>
            </div>
          )}
        </div>
      </ManagementPanel>

      {/* Prerequisite section */}
      <ManagementPanel title="Conditional Unlocking" style={{ marginBottom: "1.25rem" }}>
        <div className="course-management-form course-management-form-single">
          <div className="course-management-inline-note course-management-field-full">
            <strong>How it works</strong>
            <span>Learners must complete the selected module before this one becomes accessible.</span>
          </div>

          {eligiblePrerequisiteModules.length === 0 ? (
            <p className="course-management-field-full" style={{ color: "#64748b", fontSize: "0.9rem" }}>
              No earlier modules available. Add modules before this one to set a prerequisite.
            </p>
          ) : (
            <label className="course-management-field course-management-field-full">
              <span>Required prerequisite module</span>
              <select
                value={selectedPrerequisiteUuid}
                onChange={(e) => setSelectedPrerequisiteUuid(e.target.value)}
              >
                <option value="">— None (always accessible) —</option>
                {eligiblePrerequisiteModules.map((m) => (
                  <option key={m.moduleUuid} value={m.moduleUuid}>
                    {m.sortOrder}. {m.title}
                  </option>
                ))}
              </select>
            </label>
          )}

          {prerequisiteError ? (
            <div className="course-management-inline-alert course-management-field-full">
              <strong>Unable to update prerequisite.</strong>
              <span>{prerequisiteError}</span>
            </div>
          ) : null}
          {prerequisiteSuccess ? (
            <p className="course-management-inline-success">{prerequisiteSuccess}</p>
          ) : null}

          {eligiblePrerequisiteModules.length > 0 ? (
            <div className="course-management-form-actions course-management-field-full">
              <button
                type="button"
                className="course-management-action-button course-management-action-button-primary"
                onClick={() => void handlePrerequisiteSave()}
                disabled={isSavingPrerequisite}
              >
                {isSavingPrerequisite ? "Saving..." : "Save prerequisite"}
              </button>
            </div>
          ) : null}
        </div>
      </ManagementPanel>

      <ManagementPanel title="Short-answer assessment" style={{ marginBottom: "1.25rem" }}>
        <Link
          to={`/course/${course.courseUuid}/management/modules/${module.moduleUuid}/short-answer${managementSearchSuffix}`}
          className="course-management-create-module-card"
        >
          <span className="course-management-create-module-plus" aria-hidden="true" />
          <strong>Manage short-answer assessment</strong>
        </Link>
      </ManagementPanel>

      {/* Quiz section */}
      <ManagementPanel title="Quiz">
        {quiz ? (
          <div className="course-management-material-grid">
            <Link
              to={`/course/${course.courseUuid}/management/modules/${module.moduleUuid}/quiz${managementSearchSuffix}`}
              className="material-resource-card material-resource-card-quiz material-resource-card-linkable"
              style={{ textDecoration: "none" }}
            >
              <div className="material-resource-card-icon">
                <FaClipboardList aria-hidden="true" />
              </div>
              <div className="material-resource-card-body">
                <strong>{quiz.title || "Module Quiz"}</strong>
                <div className="material-resource-card-meta">
                  <span>Quiz</span>
                  <span>{quiz.status}</span>
                </div>
              </div>
              <div className="material-resource-card-action">
                {quiz.status === "published" && (
                  <span className="material-resource-card-status-icon material-resource-card-status-published" title="Published" aria-label="Published">
                    <FaCheckCircle aria-hidden="true" />
                  </span>
                )}
              </div>
            </Link>
          </div>
        ) : (
          <Link
            to={`/course/${course.courseUuid}/management/modules/${module.moduleUuid}/quiz${managementSearchSuffix}`}
            className="course-management-create-module-card"
          >
            <span className="course-management-create-module-plus" aria-hidden="true" />
            <strong>Create quiz</strong>
          </Link>
        )}
      </ManagementPanel>
    </section>
  );
}

export default CourseManagementModuleDetailPage;
