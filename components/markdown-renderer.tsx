"use client";

import React, { useMemo, useState } from "react";
import { Braces, ChevronRight, Copy, Check } from "lucide-react";

interface MarkdownRendererProps {
  content: string;
}

export function MarkdownRenderer({ content }: MarkdownRendererProps) {
  const renderedElements = useMemo(() => {
    if (!content) return null;

    const lines = content.split("\n");
    const elements: React.ReactNode[] = [];
    let inCodeBlock = false;
    let codeLanguage = "";
    let codeLines: string[] = [];
    let listItems: string[] = [];

    const flushList = (key: number) => {
      if (listItems.length > 0) {
        elements.push(
          <ul key={`ul-${key}`} className="my-3 list-disc pl-6 space-y-1.5 text-sm text-ink/75">
            {listItems.map((item, idx) => (
              <li key={idx} className="leading-relaxed">{parseInlineMarkdown(item)}</li>
            ))}
          </ul>
        );
        listItems = [];
      }
    };

    for (let i = 0; i < lines.length; i++) {
      const line = lines[i];

      // Handle Code Blocks
      if (line.trim().startsWith("```")) {
        if (inCodeBlock) {
          // Close code block
          const codeText = codeLines.join("\n");
          elements.push(
            <CodeBlockCard key={`code-${i}`} code={codeText} language={codeLanguage} />
          );
          codeLines = [];
          inCodeBlock = false;
        } else {
          // Open code block
          flushList(i);
          inCodeBlock = true;
          codeLanguage = line.trim().substring(3).toLowerCase();
        }
        continue;
      }

      if (inCodeBlock) {
        codeLines.push(line);
        continue;
      }

      // Handle Headers
      if (line.startsWith("# ")) {
        flushList(i);
        elements.push(
          <h1 key={`h1-${i}`} className="display text-3xl font-black mt-8 mb-4 text-ink border-b border-ink/10 pb-2">
            {parseInlineMarkdown(line.substring(2))}
          </h1>
        );
      } else if (line.startsWith("## ")) {
        flushList(i);
        elements.push(
          <h2 key={`h2-${i}`} className="display text-2xl font-bold mt-7 mb-3 text-ink">
            {parseInlineMarkdown(line.substring(3))}
          </h2>
        );
      } else if (line.startsWith("### ")) {
        flushList(i);
        elements.push(
          <h3 key={`h3-${i}`} className="font-bold text-lg mt-5 mb-2 text-ink">
            {parseInlineMarkdown(line.substring(4))}
          </h3>
        );
      }
      // Handle Bullet Lists
      else if (line.trim().startsWith("- ") || line.trim().startsWith("* ")) {
        const itemContent = line.trim().substring(2);
        listItems.push(itemContent);
      }
      // Handle Blockquotes / Alerts
      else if (line.trim().startsWith(">")) {
        flushList(i);
        // Basic blockquote parsing
        const quoteContent = line.trim().substring(1).trim();
        elements.push(
          <blockquote key={`quote-${i}`} className="my-4 border-l-4 border-ember bg-white/40 px-4 py-3 rounded-r-xl italic text-sm text-ink/75">
            {parseInlineMarkdown(quoteContent)}
          </blockquote>
        );
      }
      // Handle Horizontal Rule
      else if (line.trim() === "---") {
        flushList(i);
        elements.push(<hr key={`hr-${i}`} className="my-6 border-ink/10" />);
      }
      // Handle Normal Paragraphs
      else if (line.trim() !== "") {
        flushList(i);
        elements.push(
          <p key={`p-${i}`} className="text-sm leading-6 text-ink/70 my-3.5">
            {parseInlineMarkdown(line)}
          </p>
        );
      } else {
        // Blank line closes lists
        flushList(i);
      }
    }

    // Flush any trailing lists
    flushList(lines.length);

    return elements;
  }, [content]);

  return <div className="markdown-body reveal">{renderedElements}</div>;
}

/**
 * Basic inline formatter for strong, italic, code, and links.
 */
function parseInlineMarkdown(text: string): React.ReactNode[] {
  // Regex to split on bold, italic, code blocks, and markdown links
  const tokenRegex = /(\*\*.*?\*\*|\*.*?\*|`.*?`|\[.*?\]\(.*?\))/g;
  const parts = text.split(tokenRegex);

  return parts.map((part, index) => {
    if (part.startsWith("**") && part.endsWith("**")) {
      return <strong key={index} className="font-bold text-ink">{part.slice(2, -2)}</strong>;
    }
    if (part.startsWith("*") && part.endsWith("*")) {
      return <em key={index} className="italic text-ink/80">{part.slice(1, -1)}</em>;
    }
    if (part.startsWith("`") && part.endsWith("`")) {
      return <code key={index} className="font-mono text-xs font-bold bg-white/60 border border-ink/10 px-1 py-0.5 rounded text-ember">{part.slice(1, -1)}</code>;
    }
    if (part.startsWith("[") && part.includes("](")) {
      const match = part.match(/\[(.*?)\]\((.*?)\)/);
      if (match) {
        const linkText = match[1];
        const linkUrl = match[2];
        return (
          <a
            key={index}
            href={linkUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="font-bold text-ember hover:underline"
          >
            {linkText}
          </a>
        );
      }
    }
    return part;
  });
}

function CodeBlockCard({ code, language }: { code: string; language: string }) {
  const [copied, setCopied] = useState(false);

  const copy = () => {
    navigator.clipboard?.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  };

  return (
    <div className="card overflow-hidden my-4">
      <div className="flex items-center justify-between border-b border-ink/10 bg-[#ebe6d8] px-4 py-2">
        <div className="flex items-center gap-2">
          <Braces size={13} className="text-ink/40" />
          <span className="font-mono text-[10px] font-bold uppercase tracking-wider text-ink/50">{language || "code"}</span>
        </div>
        <button
          onClick={copy}
          className="flex items-center gap-1 text-[9px] font-bold text-ink/45 hover:text-ink hover:bg-white/40 px-2 py-1 rounded"
        >
          {copied ? <Check size={11} className="text-mint" /> : <Copy size={11} />}
          {copied ? "Copied!" : "Copy"}
        </button>
      </div>
      <pre className="overflow-x-auto bg-[#2b2f2a] p-4 text-[11px] leading-relaxed text-[#eae5d9] font-mono no-scrollbar">
        <code>{code}</code>
      </pre>
    </div>
  );
}
