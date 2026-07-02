import type { IconType } from "react-icons";
import type { ReactNode } from "react";
import {
  FaArchive,
  FaCheckCircle,
  FaCode,
  FaFileAlt,
  FaFileArchive,
  FaFileAudio,
  FaFileCsv,
  FaFileExcel,
  FaFileImage,
  FaFilePdf,
  FaFilePowerpoint,
  FaFileVideo,
  FaFileWord,
  FaGlobe,
  FaLink,
  FaRegClock,
} from "react-icons/fa";

import type { CourseMaterial } from "../../types/course";
import type { CourseModule } from "../../types/course";

type MaterialVisual = {
  icon: IconType;
  label: string;
  toneClassName: string;
};

function getExtension(value: string) {
  const cleanValue = value.split("?")[0]?.split("#")[0] ?? "";
  const lastDotIndex = cleanValue.lastIndexOf(".");
  return lastDotIndex >= 0 ? cleanValue.slice(lastDotIndex + 1).toLowerCase() : "";
}

function getMaterialVisual(material: CourseMaterial): MaterialVisual {
  const combinedType = `${material.materialType} ${material.title} ${material.resourceUrl}`.toLowerCase();
  const extension = getExtension(material.resourceUrl || material.title);

  if (combinedType.includes("pdf") || extension === "pdf") {
    return { icon: FaFilePdf, label: "文档", toneClassName: "material-resource-card-pdf" };
  }

  if (["doc", "docx"].includes(extension) || combinedType.includes("word")) {
    return { icon: FaFileWord, label: "文档", toneClassName: "material-resource-card-word" };
  }

  if (["ppt", "pptx"].includes(extension) || combinedType.includes("powerpoint") || combinedType.includes("slide")) {
    return { icon: FaFilePowerpoint, label: "演示文稿", toneClassName: "material-resource-card-powerpoint" };
  }

  if (["xls", "xlsx"].includes(extension) || combinedType.includes("excel") || combinedType.includes("spreadsheet")) {
    return { icon: FaFileExcel, label: "表格", toneClassName: "material-resource-card-excel" };
  }

  if (extension === "csv" || combinedType.includes("csv")) {
    return { icon: FaFileCsv, label: "表格数据", toneClassName: "material-resource-card-csv" };
  }

  if (["png", "jpg", "jpeg", "gif", "webp", "svg", "bmp"].includes(extension) || combinedType.includes("image")) {
    return { icon: FaFileImage, label: "图片", toneClassName: "material-resource-card-image" };
  }

  if (["mp4", "mov", "avi", "mkv", "webm"].includes(extension) || combinedType.includes("video")) {
    return { icon: FaFileVideo, label: "视频", toneClassName: "material-resource-card-video" };
  }

  if (["mp3", "wav", "m4a", "aac", "ogg"].includes(extension) || combinedType.includes("audio")) {
    return { icon: FaFileAudio, label: "音频", toneClassName: "material-resource-card-audio" };
  }

  if (
    ["zip", "rar", "7z", "tar", "gz"].includes(extension) ||
    combinedType.includes("archive") ||
    combinedType.includes("zip")
  ) {
    return { icon: FaFileArchive, label: "压缩包", toneClassName: "material-resource-card-archive" };
  }

  if (
    ["py", "js", "ts", "tsx", "jsx", "java", "c", "cpp", "cs", "html", "css", "json", "sql", "sh"].includes(extension) ||
    combinedType.includes("code")
  ) {
    return { icon: FaCode, label: "代码", toneClassName: "material-resource-card-code" };
  }

  if (combinedType.includes("http://") || combinedType.includes("https://")) {
    return extension ? { icon: FaLink, label: extension.toUpperCase(), toneClassName: "material-resource-card-link" } : { icon: FaGlobe, label: "链接", toneClassName: "material-resource-card-link" };
  }

  if (["txt", "md", "rtf"].includes(extension) || combinedType.includes("text")) {
    return { icon: FaFileAlt, label: extension ? extension.toUpperCase() : "文本", toneClassName: "material-resource-card-text" };
  }

  return {
    icon: FaFileAlt,
    label: material.materialType || (extension ? extension.toUpperCase() : "文件"),
    toneClassName: "material-resource-card-default",
  };
}

type MaterialResourceCardProps = {
  material: CourseMaterial;
  moduleStatus?: CourseModule["status"];
  trailingAction?: ReactNode;
};

function MaterialResourceCard({ material, moduleStatus, trailingAction }: MaterialResourceCardProps) {
  const visual = getMaterialVisual(material);
  const Icon = visual.icon;
  const hasUrl = Boolean(material.resourceUrl);
  const normalizedMaterialType = material.materialType.trim().toLowerCase();
  const shouldShowMaterialTypeTag =
    Boolean(normalizedMaterialType) && normalizedMaterialType !== visual.label.trim().toLowerCase();
  const statusIcon =
    moduleStatus === "available"
      ? { icon: FaCheckCircle, label: "已发布", className: "material-resource-card-status-published" }
      : moduleStatus === "locked"
        ? { icon: FaArchive, label: "已归档", className: "material-resource-card-status-archived" }
        : { icon: FaRegClock, label: "草稿", className: "material-resource-card-status-draft" };
  const StatusIcon = statusIcon.icon;
  const content = (
    <>
      <div className="material-resource-card-icon">
        <Icon aria-hidden="true" />
      </div>

      <div className="material-resource-card-body">
        <strong>{material.title}</strong>
        <div className="material-resource-card-meta">
          <span>{visual.label}</span>
          {shouldShowMaterialTypeTag ? <span>{material.materialType}</span> : null}
        </div>
      </div>
    </>
  );

  if (trailingAction) {
    return (
      <div className={`material-resource-card material-resource-card-with-trailing-action ${visual.toneClassName}`}>
        {hasUrl ? (
          <a
            className="material-resource-card-main-link"
            href={material.resourceUrl}
            target="_blank"
            rel="noreferrer noopener"
          >
            {content}
          </a>
        ) : (
          <div className="material-resource-card-main-link material-resource-card-main-link-static">
            {content}
          </div>
        )}

        <div className="material-resource-card-action">
          {moduleStatus ? (
            <span
              className={`material-resource-card-status-icon ${statusIcon.className}`}
              title={statusIcon.label}
              aria-label={statusIcon.label}
            >
              <StatusIcon aria-hidden="true" />
            </span>
          ) : null}
          {!hasUrl ? <span>不可用</span> : null}
          {trailingAction}
        </div>
      </div>
    );
  }

  const Wrapper = hasUrl ? "a" : "div";

  return (
    <Wrapper
      className={`material-resource-card ${visual.toneClassName}${hasUrl ? " material-resource-card-linkable" : ""}`}
      href={hasUrl ? material.resourceUrl : undefined}
      target={hasUrl ? "_blank" : undefined}
      rel={hasUrl ? "noreferrer noopener" : undefined}
    >
      {content}
      <div className="material-resource-card-action">
        {moduleStatus ? (
          <span
            className={`material-resource-card-status-icon ${statusIcon.className}`}
            title={statusIcon.label}
            aria-label={statusIcon.label}
          >
            <StatusIcon aria-hidden="true" />
          </span>
        ) : null}
        {!hasUrl ? <span>不可用</span> : null}
      </div>
    </Wrapper>
  );
}

export default MaterialResourceCard;
