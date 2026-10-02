/* Markdown 渲染：晨报 / 周月报 / 知识库回答统一走这里，保证排版一致。 */
import { useMemo } from "react";
import { marked } from "marked";

marked.setOptions({ gfm: true, breaks: true });

/** 把一段 Markdown 渲染成 HTML，并让所有链接在新标签页打开。 */
export function mdToHtml(md) {
  if (!md) return "";
  let html = marked.parse(String(md));
  html = html.replace(/<a href=/g, '<a target="_blank" rel="noopener noreferrer" href=');
  return html;
}

export default function Markdown({ children, className = "" }) {
  const html = useMemo(() => mdToHtml(children), [children]);
  if (!children) return null;
  return (
    <div
      className={`md-body ${className}`}
      dangerouslySetInnerHTML={{ __html: html }}
    />
  );
}
