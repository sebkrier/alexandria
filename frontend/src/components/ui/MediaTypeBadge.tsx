"use client";

import { clsx } from "clsx";
import {
  FileText,
  GraduationCap,
  PlayCircle,
  PenLine,
  FileDown,
  Mail,
} from "lucide-react";
import type { MediaType } from "@/types";

interface MediaTypeBadgeProps {
  type: MediaType;
  className?: string;
}

const MEDIA_TYPE_CONFIG: Record<
  MediaType,
  {
    label: string;
    icon: typeof FileText;
    bgColor: string;
    textColor: string;
  }
> = {
  article: {
    label: "Article",
    icon: FileText,
    bgColor: "bg-gray-500/20",
    textColor: "text-gray-400",
  },
  paper: {
    label: "Paper",
    icon: GraduationCap,
    bgColor: "bg-blue-500/20",
    textColor: "text-blue-400",
  },
  video: {
    label: "Video",
    icon: PlayCircle,
    bgColor: "bg-red-500/20",
    textColor: "text-red-400",
  },
  blog: {
    label: "Blog",
    icon: PenLine,
    bgColor: "bg-green-500/20",
    textColor: "text-green-400",
  },
  pdf: {
    label: "PDF",
    icon: FileDown,
    bgColor: "bg-orange-500/20",
    textColor: "text-orange-400",
  },
  newsletter: {
    label: "Newsletter",
    icon: Mail,
    bgColor: "bg-purple-500/20",
    textColor: "text-purple-400",
  },
};

export function MediaTypeBadge({ type, className }: MediaTypeBadgeProps) {
  const config = MEDIA_TYPE_CONFIG[type] || MEDIA_TYPE_CONFIG.article;
  const Icon = config.icon;

  return (
    <span
      className={clsx(
        "inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-xs font-medium",
        config.bgColor,
        config.textColor,
        className
      )}
    >
      <Icon className="w-3 h-3" />
      <span>{config.label}</span>
    </span>
  );
}
