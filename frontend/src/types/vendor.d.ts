declare module "react-markdown" {
  import type { ComponentType } from "react";

  type ReactMarkdownProps = {
    children?: string;
    remarkPlugins?: unknown[];
  };

  const ReactMarkdown: ComponentType<ReactMarkdownProps>;
  export default ReactMarkdown;
}

declare module "remark-gfm" {
  const remarkGfm: unknown;
  export default remarkGfm;
}
