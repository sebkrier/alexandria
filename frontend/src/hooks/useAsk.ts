"use client";

import { useMutation } from "@tanstack/react-query";
import { api } from "@/lib/api";
import toast from "react-hot-toast";

export function useAskQuestion() {
  return useMutation({
    mutationFn: (question: string) => api.askQuestion(question),
    onError: (error: Error) => {
      toast.error(error.message || "Failed to get answer");
    },
  });
}
