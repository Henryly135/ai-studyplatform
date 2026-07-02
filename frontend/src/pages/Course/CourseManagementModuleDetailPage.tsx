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
import { LuTrash2, LuX } from "react-icons/lu";

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
    return "已发布";
  }

  if (status === "locked") {
    return "已归档";
  }

  return "草稿";
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
  const [isModuleDeleteModalOpen, setIsModuleDeleteModalOpen] = useState(false);
  const [isDeletingModule, setIsDeletingModule] = useState(false);
  const [deleteModuleError, setDeleteModuleError] = useState<string | null>(null);
  const [pendingMaterialDelete, setPendingMaterialDelete] = useState<{
    materialUuid: string;
    materialTitle: string;
  } | null>(null);
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

  useEffect(() => {
    if (!isModuleDeleteModalOpen && !pendingMaterialDelete) {
      return;
    }

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key !== "Escape" || isDeletingModule || deletingMaterialUuid) {
        return;
      }

      setIsModuleDeleteModalOpen(false);
      setPendingMaterialDelete(null);
      setDeleteModuleError(null);
      setDeleteMaterialError(null);
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => {
      window.removeEventListener("keydown", handleKeyDown);
    };
  }, [deletingMaterialUuid, isDeletingModule, isModuleDeleteModalOpen, pendingMaterialDelete]);

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

  const openModuleDeleteModal = () => {
    if (isDeletingModule) {
      return;
    }

    setDeleteModuleError(null);
    setIsModuleDeleteModalOpen(true);
  };

  const closeModuleDeleteModal = () => {
    if (isDeletingModule) {
      return;
    }

    setIsModuleDeleteModalOpen(false);
    setDeleteModuleError(null);
  };

  const handleModuleDelete = async () => {
    if (!isModuleDeleteModalOpen || isDeletingModule) {
      return;
    }

    setIsDeletingModule(true);
    setDeleteModuleError(null);

    try {
      await deleteManagedModule(course.courseUuid, module.moduleUuid);
      await refreshCourse();
      setIsModuleDeleteModalOpen(false);
      navigate(`/course/${course.courseUuid}/management/modules${managementSearchSuffix}`, { replace: true });
    } catch (error) {
      setDeleteModuleError(error instanceof Error ? error.message : "Failed to delete module.");
    } finally {
      setIsDeletingModule(false);
    }
  };

  const openMaterialDeleteModal = (materialUuid: string, materialTitle: string) => {
    if (deletingMaterialUuid) {
      return;
    }

    setDeleteMaterialError(null);
    setPendingMaterialDelete({ materialUuid, materialTitle });
  };

  const closeMaterialDeleteModal = () => {
    if (deletingMaterialUuid) {
      return;
    }

    setPendingMaterialDelete(null);
    setDeleteMaterialError(null);
  };

  const handleMaterialDelete = async () => {
    if (!pendingMaterialDelete || deletingMaterialUuid) {
      return;
    }

    setDeletingMaterialUuid(pendingMaterialDelete.materialUuid);
    setDeleteMaterialError(null);

    try {
      await deleteManagedModuleMaterial(course.courseUuid, module.moduleUuid, pendingMaterialDelete.materialUuid);
      await refreshCourse();
      emitAppRefresh({ scope: "course:materials", courseUuid: course.courseUuid, moduleUuid: module.moduleUuid });
      emitAppRefresh({ scope: "course:detail", courseUuid: course.courseUuid, moduleUuid: module.moduleUuid });
      setPendingMaterialDelete(null);
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
          <strong>上传完成</strong>
          <span>{uploadToastSuccess}</span>
        </div>
      ) : null}

      <Link to={`/course/${course.courseUuid}/management/modules${managementSearchSuffix}`} className="course-management-back-link">返回模块
      </Link>

      <div className="course-management-section-heading">
        <div>
          <span className="course-surface-badge">模块详情</span>
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
              onClick={openModuleDeleteModal}
              disabled={isDeletingModule}
            >
              {isDeletingModule ? "Deleting..." : "Delete module"}
            </button>
          </div>
          <p>编辑模块内容、完善教学说明，并为该模块上传新资料。</p>
          {publishError ? (
            <div className="course-management-inline-alert">
              <strong>无法发布模块。</strong>
              <span>{publishError}</span>
            </div>
          ) : null}
          {publishSuccess ? <p className="course-management-inline-success">{publishSuccess}</p> : null}
        </div>
      </div>

      <div className="course-management-grid">
        <ManagementPanel title="模块内容">
          <form className="course-management-form course-management-form-single" onSubmit={handleModuleSave}>
            <label className="course-management-field course-management-field-full">
              <span>标题</span>
              <input value={title} onChange={(event) => setTitle(event.target.value)} required />
            </label>

            <label className="course-management-field course-management-field-full">
              <span>描述</span>
              <textarea value={description} onChange={(event) => setDescription(event.target.value)} rows={4} />
            </label>

            <label className="course-management-field course-management-field-full">
              <span>内容</span>
              <textarea value={content} onChange={(event) => setContent(event.target.value)} rows={8} />
            </label>

            <label className="course-management-field">
              <span>预计分钟数</span>
              <input
                type="number"
                min="1"
                value={estimatedMinutes}
                onChange={(event) => setEstimatedMinutes(event.target.value)}
              />
            </label>

            {saveError ? (
              <div className="course-management-inline-alert course-management-field-full">
                <strong>无法更新模块。</strong>
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
                {isSavingModule ? "保存中..." : "更新模块"}
              </button>
            </div>
          </form>
        </ManagementPanel>

        <ManagementPanel title="上传资料">
          <form className="course-management-form course-management-form-single" onSubmit={handleMaterialUpload}>
            <div className="course-management-inline-note course-management-field-full">
              <strong>上传顺序</strong>
              <span>新资料会添加到该模块资料列表末尾。</span>
            </div>

            {isPublishedModule ? (
              <div className="course-management-inline-warning course-management-field-full">
                <strong>已发布模块提示</strong>
                <span>
                  该模块已发布。这里上传的新资料会在上传后立即发布。
                </span>
              </div>
            ) : null}

            <label className="course-management-field course-management-field-full">
              <span>资料标题</span>
              <input value={materialTitle} onChange={(event) => setMaterialTitle(event.target.value)} />
            </label>

            <label className="course-management-field">
              <span>资料类型</span>
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
                <span>我理解该资料会在上传后立即发布。</span>
              </label>
            ) : null}

            {uploadError ? (
              <div className="course-management-inline-alert course-management-field-full">
                <strong>无法上传资料。</strong>
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
                  <span>{uploadStatus || "上传中..."}</span>
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
                {isUploading ? "上传中..." : "上传资料"}
              </button>
            </div>
          </form>
        </ManagementPanel>
      </div>

      <ManagementPanel title="当前资料" style={{ marginBottom: "1.25rem" }}>
        <div className="course-management-material-grid">
          {module.materials.map((material) => (
            <div key={material.materialUuid} className="course-management-material-card-with-actions">
              <button
                type="button"
                className="course-management-material-delete-icon"
                onClick={() => openMaterialDeleteModal(material.materialUuid, material.title)}
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
              <strong>暂无资料</strong>
              <p>请使用上方表单上传文件。</p>
            </div>
          )}
        </div>
      </ManagementPanel>

      {/* Prerequisite section */}
      <ManagementPanel title="条件解锁" style={{ marginBottom: "1.25rem" }}>
        <div className="course-management-form course-management-form-single">
          <div className="course-management-inline-note course-management-field-full">
            <strong>工作方式</strong>
            <span>学生必须先完成选中的模块，才能访问当前模块。</span>
          </div>

          {eligiblePrerequisiteModules.length === 0 ? (
            <p className="course-management-field-full" style={{ color: "#64748b", fontSize: "0.9rem" }}>暂无更早的模块。请先在当前模块之前添加模块，再设置前置条件。
            </p>
          ) : (
            <label className="course-management-field course-management-field-full">
              <span>必修前置模块</span>
              <select
                value={selectedPrerequisiteUuid}
                onChange={(e) => setSelectedPrerequisiteUuid(e.target.value)}
              >
                <option value="">无（始终可访问）</option>
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
              <strong>无法更新前置条件。</strong>
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
                {isSavingPrerequisite ? "保存中..." : "Save prerequisite"}
              </button>
            </div>
          ) : null}
        </div>
      </ManagementPanel>

      {/* Quiz section */}
      <ManagementPanel title="测验">
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
                  <span>测验</span>
                  <span>{quiz.status}</span>
                </div>
              </div>
              <div className="material-resource-card-action">
                {quiz.status === "published" && (
                  <span className="material-resource-card-status-icon material-resource-card-status-published" title="已发布" aria-label="已发布">
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
            <strong>创建测验</strong>
          </Link>
        )}
      </ManagementPanel>

      {isModuleDeleteModalOpen ? (
        <div className="course-management-modal-overlay" role="presentation">
          <div
            className="course-management-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-module-detail-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="course-management-modal-header">
              <div>
                <span className="course-surface-badge">删除模块</span>
                <h3 id="delete-module-detail-title">删除这个模块？</h3>
                <p className="course-management-modal-status">这将永久删除该模块及其所有关联资料。
                </p>
              </div>
              <button
                type="button"
                className="course-management-modal-close"
                onClick={closeModuleDeleteModal}
                aria-label="关闭删除模块窗口"
                disabled={isDeletingModule}
              >
                <LuX size={18} aria-hidden="true" />
              </button>
            </div>

            <div className="course-management-form course-management-form-single">
              <div className="course-management-inline-alert course-management-field-full">
                <strong>{module.title}</strong>
                <span>删除该模块后无法撤销。</span>
              </div>

              {deleteModuleError ? (
                <div className="course-management-inline-alert course-management-field-full">
                  <strong>无法删除模块。</strong>
                  <span>{deleteModuleError}</span>
                </div>
              ) : null}

              <div className="course-management-form-actions course-management-field-full">
                <button
                  type="button"
                  className="course-management-action-button"
                  onClick={closeModuleDeleteModal}
                  disabled={isDeletingModule}
                >保留模块
                </button>
                <button
                  type="button"
                  className="course-management-action-button course-management-action-button-danger"
                  onClick={() => void handleModuleDelete()}
                  disabled={isDeletingModule}
                >
                  {isDeletingModule ? "Deleting..." : "永久删除"}
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}

      {pendingMaterialDelete ? (
        <div className="course-management-modal-overlay" role="presentation">
          <div
            className="course-management-modal"
            role="dialog"
            aria-modal="true"
            aria-labelledby="delete-module-material-title"
            onClick={(event) => event.stopPropagation()}
          >
            <div className="course-management-modal-header">
              <div>
                <span className="course-surface-badge">删除资料</span>
                <h3 id="delete-module-material-title">删除这份资料？</h3>
                <p className="course-management-modal-status">这会从模块中删除资料文件和记录。
                </p>
              </div>
              <button
                type="button"
                className="course-management-modal-close"
                onClick={closeMaterialDeleteModal}
                aria-label="关闭删除资料窗口"
                disabled={deletingMaterialUuid !== null}
              >
                <LuX size={18} aria-hidden="true" />
              </button>
            </div>

            <div className="course-management-form course-management-form-single">
              <div className="course-management-inline-alert course-management-field-full">
                <strong>{pendingMaterialDelete.materialTitle}</strong>
                <span>所属模块： {module.title}</span>
              </div>

              {deleteMaterialError ? (
                <div className="course-management-inline-alert course-management-field-full">
                  <strong>无法删除资料。</strong>
                  <span>{deleteMaterialError}</span>
                </div>
              ) : null}

              <div className="course-management-form-actions course-management-field-full">
                <button
                  type="button"
                  className="course-management-action-button"
                  onClick={closeMaterialDeleteModal}
                  disabled={deletingMaterialUuid !== null}
                >保留资料
                </button>
                <button
                  type="button"
                  className="course-management-action-button course-management-action-button-danger"
                  onClick={() => void handleMaterialDelete()}
                  disabled={deletingMaterialUuid !== null}
                >
                  {deletingMaterialUuid ? "Deleting..." : "永久删除"}
                </button>
              </div>
            </div>
          </div>
        </div>
      ) : null}
    </section>
  );
}

export default CourseManagementModuleDetailPage;
