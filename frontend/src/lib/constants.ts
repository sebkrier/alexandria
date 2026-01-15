/**
 * Frontend application constants.
 */

// LocalStorage keys
export const STORAGE_KEYS = {
  KEYBOARD_HINTS_DISMISSED: "alexandria-keyboard-hints-dismissed",
  VIEW_MODE: "alexandria-view-mode",
  SIDEBAR_COLLAPSED: "alexandria-sidebar-collapsed",
} as const;

// API configuration
export const API_CONFIG = {
  BASE_URL: process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000",
  TIMEOUT: 30000,
} as const;

// Pagination defaults
export const PAGINATION = {
  DEFAULT_PAGE_SIZE: 20,
  MAX_PAGE_SIZE: 100,
} as const;

// UI constants
export const UI = {
  DEBOUNCE_MS: 300,
  TRANSITION_MS: 150,
  TOAST_DURATION: 4000,
} as const;
