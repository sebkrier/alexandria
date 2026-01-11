import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import type { CreateProviderRequest } from "@/types";
import toast from "react-hot-toast";

export function useAvailableProviders() {
  return useQuery({
    queryKey: ["available-providers"],
    queryFn: () => api.getAvailableProviders(),
  });
}

export function useProviders() {
  return useQuery({
    queryKey: ["providers"],
    queryFn: () => api.getProviders(),
  });
}

export function useCreateProvider() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (data: CreateProviderRequest) => api.createProvider(data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["providers"] });
      toast.success("AI provider added");
    },
    onError: (error: Error) => {
      toast.error(`Failed to add provider: ${error.message}`);
    },
  });
}

export function useUpdateProvider() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      updates,
    }: {
      id: string;
      updates: {
        display_name?: string;
        model_id?: string;
        api_key?: string;
        is_default?: boolean;
        is_active?: boolean;
      };
    }) => api.updateProvider(id, updates),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["providers"] });
      toast.success("Provider updated");
    },
    onError: (error: Error) => {
      toast.error(`Failed to update provider: ${error.message}`);
    },
  });
}

export function useDeleteProvider() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.deleteProvider(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["providers"] });
      toast.success("Provider deleted");
    },
    onError: (error: Error) => {
      toast.error(`Failed to delete provider: ${error.message}`);
    },
  });
}

export function useTestProvider() {
  return useMutation({
    mutationFn: (id: string) => api.testProvider(id),
    onSuccess: (result) => {
      if (result.success) {
        toast.success(result.message);
      } else {
        toast.error(result.message);
      }
    },
    onError: (error: Error) => {
      toast.error(`Test failed: ${error.message}`);
    },
  });
}

export function useColors() {
  return useQuery({
    queryKey: ["colors"],
    queryFn: () => api.getColors(),
  });
}

export function useSummaryPrompt() {
  return useQuery({
    queryKey: ["summary-prompt"],
    queryFn: () => api.getSummaryPrompt(),
  });
}
