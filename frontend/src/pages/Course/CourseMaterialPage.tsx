import { useEffect } from "react";
import { Navigate, useLocation, useOutletContext, useParams } from "react-router-dom";

import { updateModuleProgress } from "../../services/course";
import type { CourseMaterial } from "../../types/course";
import type { CourseOutletContext } from "./CourseLayout";

function formatFileSize(value: unknown) {
  if (typeof value !== "number" || !Number.isFinite(value) || value <= 0) {
    return null;
  }

  if (value < 1024) {
    return `${value} B`;
  }

  const units = ["KB", "MB", "GB"];
  let size = value / 1024;
  let unitIndex = 0;

  while (size >= 1024 && unitIndex < units.length - 1) {
    size /= 1024;
    unitIndex += 1;
  }

  return `${size.toFixed(size >= 10 ? 0 : 1)} ${units[unitIndex]}`;
}

function getFileInformation(material: CourseMaterial) {
  const metadata = material.metadataJson ?? {};
  const items = [
    {
      label: "原始文件名",
      value:
        typeof metadata.originalFilename === "string" && metadata.originalFilename.trim()
          ? metadata.originalFilename.trim()
          : null,
    },
    {
      label: "文件大小",
      value: formatFileSize(metadata.sizeBytes),
    },
    {
      label: "内容类型",
      value:
        typeof metadata.contentType === "string" && metadata.contentType.trim()
          ? metadata.contentType.trim()
          : null,
    },
  ].filter((item): item is { label: string; value: string } => Boolean(item.value));

  return items;
}

function getNormalizedContentType(material: CourseMaterial) {
  const metadata = material.metadataJson ?? {};
  return typeof metadata.contentType === "string" && metadata.contentType.trim()
    ? metadata.contentType.trim().toLowerCase()
    : "";
}

function getFileExtension(material: CourseMaterial) {
  const metadata = material.metadataJson ?? {};
  const originalFilename =
    typeof metadata.originalFilename === "string" && metadata.originalFilename.trim()
      ? metadata.originalFilename.trim().toLowerCase()
      : "";
  const rawValue = originalFilename || material.resourceUrl.trim().toLowerCase() || material.title.trim().toLowerCase();
  const cleanValue = rawValue.split("?")[0]?.split("#")[0] ?? "";
  const lastDotIndex = cleanValue.lastIndexOf(".");
  return lastDotIndex >= 0 ? cleanValue.slice(lastDotIndex + 1) : "";
}

function isVideoMaterial(material: CourseMaterial) {
  const contentType = getNormalizedContentType(material);
  const normalizedMaterialType = material.materialType.trim().toLowerCase();
  const normalizedUrl = material.resourceUrl.trim().toLowerCase();

  return (
    contentType.startsWith("video/") ||
    normalizedMaterialType === "video" ||
    [".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"].some((extension) => normalizedUrl.includes(extension))
  );
}

function isImageMaterial(material: CourseMaterial) {
  const contentType = getNormalizedContentType(material);
  const normalizedUrl = material.resourceUrl.trim().toLowerCase();

  return (
    contentType.startsWith("image/") ||
    [".jpg", ".jpeg", ".png", ".gif", ".webp", ".svg", ".bmp"].some((extension) => normalizedUrl.includes(extension))
  );
}

function isPdfMaterial(material: CourseMaterial) {
  const contentType = getNormalizedContentType(material);
  const normalizedMaterialType = material.materialType.trim().toLowerCase();
  const normalizedUrl = material.resourceUrl.trim().toLowerCase();

  return (
    contentType === "application/pdf" ||
    normalizedMaterialType === "pdf" ||
    normalizedUrl.includes(".pdf")
  );
}

function isAudioMaterial(material: CourseMaterial) {
  const contentType = getNormalizedContentType(material);
  const normalizedMaterialType = material.materialType.trim().toLowerCase();
  const normalizedUrl = material.resourceUrl.trim().toLowerCase();

  return (
    contentType.startsWith("audio/") ||
    normalizedMaterialType === "audio" ||
    [".mp3", ".wav", ".ogg", ".m4a", ".aac", ".flac"].some((extension) => normalizedUrl.includes(extension))
  );
}

function isPreviewableDocumentMaterial(material: CourseMaterial) {
  const contentType = getNormalizedContentType(material);
  const extension = getFileExtension(material);

  if (isVideoMaterial(material) || isImageMaterial(material) || isAudioMaterial(material) || isPdfMaterial(material)) {
    return true;
  }

  if (contentType.startsWith("text/")) {
    return true;
  }

  return ["txt", "md"].includes(extension);
}

function FileInformation({ material }: { material: CourseMaterial }) {
  const items = getFileInformation(material);

  if (items.length === 0) {
    return <p>暂无更多文件信息。</p>;
  }

  return (
    <div className="course-metadata-grid">
      {items.map((item) => (
        <article key={item.label} className="course-metadata-card">
          <span>{item.label}</span>
          <strong>{item.value}</strong>
        </article>
      ))}
    </div>
  );
}

function CourseMaterialPage() {
  const { course, isChatOpen, markModuleCompleted, refreshCourse } = useOutletContext<CourseOutletContext>();
  const { moduleUuid, materialUuid } = useParams();
  const location = useLocation();

  const module = course.modules.find((item) => item.moduleUuid === moduleUuid);
  const material = module?.materials.find((item) => item.materialUuid === materialUuid);

  const source = new URLSearchParams(location.search).get("from");
  const isLearnerView = source === "my-courses";
  const moduleIsCompleteable =
    module ? !module.isLocked && !module.isCompleted && !module.hasPublishedQuiz : false;
  const activeModuleUuid = module?.moduleUuid ?? null;

  useEffect(() => {
    if (!activeModuleUuid || !moduleIsCompleteable || !isLearnerView) {
      return;
    }
    void updateModuleProgress(course.courseUuid, activeModuleUuid, "completed")
      .then(() => {
        markModuleCompleted(activeModuleUuid);
        return refreshCourse();
      })
      .catch(() => {
        // Progress updates are opportunistic; the learner can continue reading the material.
      });
  }, [activeModuleUuid, course.courseUuid, isLearnerView, markModuleCompleted, moduleIsCompleteable, refreshCourse]);

  if (!module || !material) {
    return <Navigate to={`/course/${course.courseUuid}`} replace />;
  }

  const videoMaterial = isVideoMaterial(material);
  const imageMaterial = isImageMaterial(material);
  const pdfMaterial = isPdfMaterial(material);
  const audioMaterial = isAudioMaterial(material);
  const previewableDocumentMaterial = isPreviewableDocumentMaterial(material);

  return (
    <section className="course-detail-page">
      <div className={`course-material-layout${isChatOpen ? " course-material-layout-chat-open" : ""}`}>
        <article className="course-material-player-panel">
          <div className="course-panel-heading">
            <h3>{videoMaterial ? "Video lesson" : "Material preview"}</h3>
          </div>
          {material.resourceUrl ? (
            videoMaterial ? (
              <div className="course-video-stage">
                <video
                  className="course-video-player"
                  controls
                  preload="metadata"
                  playsInline
                  src={material.resourceUrl}
                >你的浏览器不支持内嵌视频播放，请使用打开资料链接。
                </video>
              </div>
            ) : imageMaterial ? (
              <div className="course-document-stage">
                <img className="course-image-viewer" src={material.resourceUrl} alt={material.title} />
              </div>
            ) : audioMaterial ? (
              <div className="course-audio-stage">
                <audio className="course-audio-player" controls preload="metadata" src={material.resourceUrl}>你的浏览器不支持内嵌音频播放，请使用打开资料链接。
                </audio>
              </div>
            ) : previewableDocumentMaterial ? (
              <div className="course-document-stage">
                <iframe
                  className="course-document-viewer"
                  title={material.title}
                  src={pdfMaterial ? `${material.resourceUrl}#view=FitH` : material.resourceUrl}
                />
              </div>
            ) : (
              <div className="course-empty-state">
                <strong>无法预览</strong>
                <p>该文件类型可以在新标签页打开或下载到设备。</p>
              </div>
            )
          ) : (
            <div className="course-empty-state">
              <strong>{videoMaterial ? "Video unavailable" : "无法预览"}</strong>
              <p>该资料当前没有可查看的资源链接。</p>
            </div>
          )}
        </article>

        {!isChatOpen ? (
          <div className="course-material-sidebar">
            <article className="course-panel">
              <div className="course-panel-heading">
                <h3>资料详情</h3>
              </div>
              <div className="course-material-detail-list">
                <p>课程： {course.title}</p>
                <p>模块： {module.title}</p>
                {material.materialType ? <p>资料类型： {material.materialType}</p> : null}
                <p>顺序： {material.sortOrder}</p>
              </div>
              {material.resourceUrl ? (
                <div className="course-material-actions">
                  <a className="course-primary-link" href={material.resourceUrl} target="_blank" rel="noreferrer">打开资料
                  </a>
                  <a className="course-secondary-link" href={material.resourceUrl} download>
                    {videoMaterial ? "Download video" : "下载文件"}
                  </a>
                </div>
              ) : null}
            </article>

            <article className="course-panel">
              <div className="course-panel-heading">
                <h3>文件信息</h3>
              </div>
              <FileInformation material={material} />
            </article>
          </div>
        ) : null}
      </div>
    </section>
  );
}

export default CourseMaterialPage;
