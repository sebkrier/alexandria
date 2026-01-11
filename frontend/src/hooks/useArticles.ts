import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useStore } from "@/lib/store";
import toast from "react-hot-toast";

export function useArticles(page = 1) {
  const { searchQuery, selectedCategoryId, selectedTagId, selectedColorId } = useStore();

  return useQuery({
    queryKey: ["articles", page, searchQuery, selectedCategoryId, selectedTagId, selectedColorId],
    queryFn: () =>
      api.getArticles({
        page,
        page_size: 20,
        search: searchQuery || undefined,
        category_id: selectedCategoryId || undefined,
        tag_id: selectedTagId || undefined,
        color_id: selectedColorId || undefined,
      }),
  });
}

export function useArticle(id: string) {
  return useQuery({
    queryKey: ["article", id],
    queryFn: () => api.getArticle(id),
    enabled: !!id,
  });
}

export function useArticleText(id: string) {
  return useQuery({
    queryKey: ["article-text", id],
    queryFn: () => api.getArticleText(id),
    enabled: !!id,
  });
}

export function useCreateArticle() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (url: string) => api.createArticleFromUrl(url),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["articles"] });
      queryClient.invalidateQueries({ queryKey: ["categories"] });
      toast.success("Article added successfully");
    },
    onError: (error: Error) => {
      toast.error(`Failed to add article: ${error.message}`);
    },
  });
}

export function useUploadArticle() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (file: File) => api.uploadArticle(file),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["articles"] });
      queryClient.invalidateQueries({ queryKey: ["categories"] });
      toast.success("PDF uploaded successfully");
    },
    onError: (error: Error) => {
      toast.error(`Failed to upload PDF: ${error.message}`);
    },
  });
}

export function useProcessArticle() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ id, providerId }: { id: string; providerId?: string }) =>
      api.processArticle(id, providerId),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ["article", id] });
      queryClient.invalidateQueries({ queryKey: ["articles"] });
      queryClient.invalidateQueries({ queryKey: ["categories"] });
      toast.success("Article processed successfully");
    },
    onError: (error: Error) => {
      toast.error(`Processing failed: ${error.message}`);
    },
  });
}

export function useUpdateArticle() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({
      id,
      updates,
    }: {
      id: string;
      updates: { title?: string; color_id?: string; category_ids?: string[]; tag_ids?: string[] };
    }) => api.updateArticle(id, updates),
    onSuccess: (_, { id }) => {
      queryClient.invalidateQueries({ queryKey: ["article", id] });
      queryClient.invalidateQueries({ queryKey: ["articles"] });
      queryClient.invalidateQueries({ queryKey: ["categories"] });
    },
    onError: (error: Error) => {
      toast.error(`Failed to update: ${error.message}`);
    },
  });
}

export function useDeleteArticle() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (id: string) => api.deleteArticle(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["articles"] });
      queryClient.invalidateQueries({ queryKey: ["categories"] });
      toast.success("Article deleted");
    },
    onError: (error: Error) => {
      toast.error(`Failed to delete: ${error.message}`);
    },
  });
}

export function useReorganizeArticles() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: (uncategorizedOnly: boolean = true) =>
      api.reorganizeArticles(uncategorizedOnly),
    onSuccess: (data) => {
      queryClient.invalidateQueries({ queryKey: ["articles"] });
      queryClient.invalidateQueries({ queryKey: ["categories"] });
      if (data.processed > 0) {
        toast.success(`Reorganized ${data.processed} articles`);
      } else {
        toast.success("No articles needed reorganization");
      }
    },
    onError: (error: Error) => {
      toast.error(`Reorganization failed: ${error.message}`);
    },
  });
}
