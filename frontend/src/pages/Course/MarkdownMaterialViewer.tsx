import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

import { loadMarkdownText } from "./markdownMaterial";

export type MarkdownViewMode = "preview" | "source";

type MarkdownLoadState =
  | { status: "loading"; content: ""; error: null }
  | { status: "ready"; content: string; error: null }
  | { status: "error"; content: ""; error: string };

type MarkdownMaterialViewerProps = {
  resourceUrl: string;
  title: string;
};

export function MarkdownMaterialDocument({
  content,
  viewMode,
}: {
  content: string;
  viewMode: MarkdownViewMode;
}) {
  if (viewMode === "source") {
    return (
      <pre className="course-markdown-source" data-view-mode="source">
        <code>{content}</code>
      </pre>
    );
  }

  return (
    <article className="course-markdown-preview" data-view-mode="preview">
      <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
    </article>
  );
}

export function MarkdownMaterialViewer({ resourceUrl, title }: MarkdownMaterialViewerProps) {
  const [viewMode, setViewMode] = useState<MarkdownViewMode>("preview");
  const [requestVersion, setRequestVersion] = useState(0);
  const [loadState, setLoadState] = useState<MarkdownLoadState>({
    status: "loading",
    content: "",
    error: null,
  });

  useEffect(() => {
    const controller = new AbortController();

    void loadMarkdownText(resourceUrl, controller.signal)
      .then((content) => {
        if (!controller.signal.aborted) {
          setLoadState({ status: "ready", content, error: null });
        }
      })
      .catch((error) => {
        if (!controller.signal.aborted) {
          setLoadState({
            status: "error",
            content: "",
            error: error instanceof Error ? error.message : "Markdown 资料加载失败。",
          });
        }
      });

    return () => {
      controller.abort();
    };
  }, [requestVersion, resourceUrl]);

  function retryLoad() {
    setLoadState({ status: "loading", content: "", error: null });
    setRequestVersion((current) => current + 1);
  }

  const viewIsReady = loadState.status === "ready";

  return (
    <div className="course-markdown-stage">
      <div className="course-markdown-toolbar" role="group" aria-label="Markdown 查看模式">
        <button
          type="button"
          className={`course-markdown-view-toggle${viewMode === "preview" ? " course-markdown-view-toggle-active" : ""}`}
          aria-pressed={viewMode === "preview"}
          disabled={!viewIsReady}
          onClick={() => setViewMode("preview")}
        >
          Preview
        </button>
        <button
          type="button"
          className={`course-markdown-view-toggle${viewMode === "source" ? " course-markdown-view-toggle-active" : ""}`}
          aria-pressed={viewMode === "source"}
          disabled={!viewIsReady}
          onClick={() => setViewMode("source")}
        >
          Source
        </button>
      </div>

      <div
        className="course-markdown-document"
        aria-busy={loadState.status === "loading"}
        aria-label={`${title} Markdown 内容`}
      >
        {loadState.status === "loading" ? (
          <div className="course-markdown-status" role="status">正在加载 Markdown 预览...</div>
        ) : null}
        {loadState.status === "error" ? (
          <div className="course-markdown-status course-markdown-status-error" role="alert">
            <strong>无法加载 Markdown 资料</strong>
            <p>{loadState.error}</p>
            <button type="button" className="course-markdown-retry" onClick={retryLoad}>重试</button>
          </div>
        ) : null}
        {loadState.status === "ready" ? (
          <MarkdownMaterialDocument content={loadState.content} viewMode={viewMode} />
        ) : null}
      </div>
    </div>
  );
}
