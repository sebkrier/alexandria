import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import toast from "react-hot-toast";

export function useUnreadList() {
  return useQuery({
    queryKey: ["unread-list"],
    queryFn: () => api.getUnreadList(),
  });
}

export function useUnreadNavigation(articleId: string | null) {
  return useQuery({
    queryKey: ["unread-navigation", articleId],
    queryFn: () => api.getUnreadNavigation(articleId!),
    enabled: !!articleId,
  });
}

export function useMarkAsRead() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: async ({
      articleId,
      colorId,
      categoryIds,
    }: {
      articleId: string;
      colorId?: string;
      categoryIds?: string[];
    }) => {
      return api.updateArticle(articleId, {
        is_read: true,
        color_id: colorId,
        category_ids: categoryIds,
      });
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["articles"] });
      queryClient.invalidateQueries({ queryKey: ["unread-list"] });
      queryClient.invalidateQueries({ queryKey: ["unread-navigation"] });
      queryClient.invalidateQueries({ queryKey: ["categories"] });
      toast.success("Marked as read");
    },
    onError: (error: Error) => {
      toast.error(`Failed to mark as read: ${error.message}`);
    },
  });
}
