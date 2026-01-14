"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { clsx } from "clsx";
import {
  Library,
  FolderTree,
  Tag,
  Settings,
  Plus,
  ChevronRight,
  ChevronDown,
  Circle,
  Palette,
  Smartphone,
} from "lucide-react";
import { useStore } from "@/lib/store";
import { useCategories } from "@/hooks/useCategories";
import { useColors } from "@/hooks/useProviders";
import { useState, useEffect } from "react";
import type { Category } from "@/types";

function CategoryItem({ category, depth = 0 }: { category: Category; depth?: number }) {
  const [expanded, setExpanded] = useState(false);
  const { selectedCategoryId, setSelectedCategoryId } = useStore();
  const hasChildren = category.children && category.children.length > 0;
  const isSelected = selectedCategoryId === category.id;
  const isParentCategory = depth === 0;

  return (
    <div>
      <button
        onClick={() => {
          if (isSelected) {
            setSelectedCategoryId(null);
          } else {
            setSelectedCategoryId(category.id);
          }
        }}
        className={clsx(
          "w-full flex items-center gap-2 px-3 py-1 text-xs rounded-lg transition-colors",
          isSelected
            ? "bg-article-blue/20 text-article-blue"
            : "text-dark-muted hover:text-dark-text hover:bg-dark-hover",
          isParentCategory && "font-medium"
        )}
        style={{ paddingLeft: `${12 + depth * 16}px` }}
      >
        {hasChildren ? (
          <button
            onClick={(e) => {
              e.stopPropagation();
              setExpanded(!expanded);
            }}
            className="p-0.5 hover:bg-dark-hover rounded"
          >
            {expanded ? (
              <ChevronDown className="w-3.5 h-3.5" />
            ) : (
              <ChevronRight className="w-3.5 h-3.5" />
            )}
          </button>
        ) : (
          <Circle className={clsx("w-2 h-2 ml-1 mr-1", isSelected ? "fill-article-blue" : "fill-dark-muted/50")} />
        )}
        <span className="flex-1 text-left truncate">{category.name}</span>
        <span className={clsx(
          "text-xs",
          isSelected ? "text-article-blue" : "text-dark-muted"
        )}>
          {category.article_count}
        </span>
      </button>
      {hasChildren && expanded && (
        <div className="border-l border-dark-border/50 ml-5">
          {category.children!.map((child) => (
            <CategoryItem key={child.id} category={child} depth={depth + 1} />
          ))}
        </div>
      )}
    </div>
  );
}

export function Sidebar() {
  const pathname = usePathname();
  const { sidebarOpen, setAddArticleModalOpen, resetFilters, selectedColorId, setSelectedColorId } = useStore();
  const { data: categories } = useCategories();
  const { data: colors } = useColors();
  const [isClicking, setIsClicking] = useState(false);

  // Change logo to red eyes during any click
  useEffect(() => {
    const handleMouseDown = () => setIsClicking(true);
    const handleMouseUp = () => setIsClicking(false);

    document.addEventListener("mousedown", handleMouseDown);
    document.addEventListener("mouseup", handleMouseUp);

    return () => {
      document.removeEventListener("mousedown", handleMouseDown);
      document.removeEventListener("mouseup", handleMouseUp);
    };
  }, []);

  if (!sidebarOpen) return null;

  const navItems = [
    { href: "/", icon: Library, label: "Library" },
    { href: "/remote", icon: Smartphone, label: "Remote Add" },
    { href: "/settings", icon: Settings, label: "Settings" },
  ];

  return (
    <aside className="w-64 h-screen bg-dark-surface border-r border-dark-border flex flex-col">
      {/* Logo */}
      <div className="px-4 py-4 border-b border-dark-border">
        <Link href="/" className="flex items-center gap-2" onClick={resetFilters}>
          <Library className="w-6 h-6 text-article-blue" />
          <span className="text-lg font-semibold text-white">Alexandria</span>
        </Link>
      </div>

      {/* Add Article/Video Button */}
      <div className="px-3 py-3">
        <button
          onClick={() => setAddArticleModalOpen(true)}
          className="w-full flex items-center justify-center gap-2 px-4 py-2.5 bg-article-blue text-white rounded-lg hover:bg-article-blue/90 transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span className="font-medium">Add Article/Video</span>
        </button>
      </div>

      {/* Navigation */}
      <nav className="px-3 py-2">
        {navItems.map((item) => {
          const isActive = pathname === item.href;
          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={resetFilters}
              className={clsx(
                "flex items-center gap-3 px-3 py-2 rounded-lg transition-colors",
                isActive
                  ? "bg-dark-hover text-white"
                  : "text-dark-muted hover:text-dark-text hover:bg-dark-hover"
              )}
            >
              <item.icon className="w-5 h-5" />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>

      {/* Categories */}
      <div className="flex-1 overflow-y-auto px-3 py-4 border-t border-dark-border">
        <div className="flex items-center justify-between mb-2 px-3">
          <span className="text-xs font-semibold text-dark-muted uppercase tracking-wider">
            Categories
          </span>
        </div>
        <div className="space-y-0.5">
          {categories?.map((category) => (
            <CategoryItem key={category.id} category={category} />
          ))}
        </div>

        {/* Colors */}
        {colors && colors.length > 0 && (
          <div className="mt-6">
            <div className="flex items-center justify-between mb-2 px-3">
              <span className="text-xs font-semibold text-dark-muted uppercase tracking-wider">
                Colors
              </span>
            </div>
            <div className="space-y-0.5">
              {colors.map((color) => {
                const isSelected = selectedColorId === color.id;
                return (
                  <button
                    key={color.id}
                    onClick={() => {
                      if (isSelected) {
                        setSelectedColorId(null);
                      } else {
                        setSelectedColorId(color.id);
                      }
                    }}
                    className={clsx(
                      "w-full flex items-center gap-2 px-3 py-1.5 text-sm rounded-lg transition-colors",
                      isSelected
                        ? "bg-article-blue/20 text-article-blue"
                        : "text-dark-muted hover:text-dark-text hover:bg-dark-hover"
                    )}
                  >
                    <div
                      className="w-4 h-4 rounded-full"
                      style={{ backgroundColor: color.hex_value }}
                    />
                    <span className="flex-1 text-left truncate">{color.name}</span>
                  </button>
                );
              })}
            </div>
          </div>
        )}
      </div>

      {/* Footer with logo */}
      <div className="px-4 py-6 border-t border-dark-border flex justify-center">
        <img
          src={isClicking ? "/logo-eyes.png" : "/logo.jpg"}
          alt="Alexandria"
          className="h-48 w-auto object-contain opacity-80"
        />
      </div>
    </aside>
  );
}
