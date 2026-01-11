"use client";

import { useRef, type TextareaHTMLAttributes } from "react";
import { clsx } from "clsx";
import { Bold, Italic, List, ListOrdered, Link, Code } from "lucide-react";

interface MarkdownEditorProps
  extends Omit<TextareaHTMLAttributes<HTMLTextAreaElement>, "onChange"> {
  value: string;
  onChange: (value: string) => void;
}

export function MarkdownEditor({
  value,
  onChange,
  className,
  ...props
}: MarkdownEditorProps) {
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  const wrapSelection = (before: string, after: string) => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selectedText = value.substring(start, end);

    const newValue =
      value.substring(0, start) +
      before +
      selectedText +
      after +
      value.substring(end);

    onChange(newValue);

    // Restore cursor position after the inserted text
    setTimeout(() => {
      textarea.focus();
      const newCursorPos = start + before.length + selectedText.length + after.length;
      textarea.setSelectionRange(
        selectedText ? newCursorPos : start + before.length,
        selectedText ? newCursorPos : start + before.length
      );
    }, 0);
  };

  const insertAtCursor = (text: string) => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const newValue = value.substring(0, start) + text + value.substring(start);
    onChange(newValue);

    setTimeout(() => {
      textarea.focus();
      const newCursorPos = start + text.length;
      textarea.setSelectionRange(newCursorPos, newCursorPos);
    }, 0);
  };

  const insertList = (ordered: boolean) => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selectedText = value.substring(start, end);

    if (selectedText) {
      // Convert selected lines to list
      const lines = selectedText.split("\n");
      const listText = lines
        .map((line, i) => (ordered ? `${i + 1}. ${line}` : `- ${line}`))
        .join("\n");
      const newValue = value.substring(0, start) + listText + value.substring(end);
      onChange(newValue);
    } else {
      // Insert new list item
      const prefix = ordered ? "1. " : "- ";
      insertAtCursor(prefix);
    }
  };

  const insertLink = () => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const start = textarea.selectionStart;
    const end = textarea.selectionEnd;
    const selectedText = value.substring(start, end);

    if (selectedText) {
      // Wrap selected text as link text
      wrapSelection("[", "](url)");
    } else {
      insertAtCursor("[link text](url)");
    }
  };

  const toolbarButtons = [
    {
      icon: Bold,
      label: "Bold",
      action: () => wrapSelection("**", "**"),
    },
    {
      icon: Italic,
      label: "Italic",
      action: () => wrapSelection("*", "*"),
    },
    {
      icon: Code,
      label: "Code",
      action: () => wrapSelection("`", "`"),
    },
    {
      icon: List,
      label: "Bullet list",
      action: () => insertList(false),
    },
    {
      icon: ListOrdered,
      label: "Numbered list",
      action: () => insertList(true),
    },
    {
      icon: Link,
      label: "Link",
      action: insertLink,
    },
  ];

  return (
    <div className="w-full">
      {/* Toolbar */}
      <div className="flex items-center gap-1 mb-1 p-1 bg-dark-bg border border-dark-border rounded-t-lg border-b-0">
        {toolbarButtons.map((button) => (
          <button
            key={button.label}
            type="button"
            onClick={button.action}
            title={button.label}
            className="p-1.5 text-dark-muted hover:text-white hover:bg-dark-hover rounded transition-colors"
          >
            <button.icon className="w-4 h-4" />
          </button>
        ))}
      </div>

      {/* Textarea */}
      <textarea
        ref={textareaRef}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className={clsx(
          "w-full px-3 py-2 bg-dark-bg border border-dark-border rounded-b-lg text-dark-text placeholder-dark-muted text-sm resize-none focus:outline-none focus:ring-1 focus:ring-article-blue",
          className
        )}
        {...props}
      />
    </div>
  );
}
