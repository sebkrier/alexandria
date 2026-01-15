import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import toast from "react-hot-toast";

export function useArticleNotes(articleId: string) {
  return useQuery({
    queryKey: ["notes", articleId],
    queryFn: () => api.getArticleNotes(articleId),
    enabled: !!articleId,
  });
}

export function useCreateNote() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ articleId, content }: { articleId: string; content: string }) =>
      api.createNote(articleId, content),
    onSuccess: (_, { articleId }) => {
      queryClient.invalidateQueries({ queryKey: ["notes", articleId] });
      queryClient.invalidateQueries({ queryKey: ["article", articleId] });
      toast.success("Note added");
    },
    onError: (error: Error) => {
      toast.error(`Failed to add note: ${error.message}`);
    },
  });
}

export function useUpdateNote() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ noteId, content }: { noteId: string; content: string; articleId: string }) =>
      api.updateNote(noteId, content),
    onSuccess: (_, { articleId }) => {
      queryClient.invalidateQueries({ queryKey: ["notes", articleId] });
      toast.success("Note updated");
    },
    onError: (error: Error) => {
      toast.error(`Failed to update note: ${error.message}`);
    },
  });
}

export function useDeleteNote() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ noteId }: { noteId: string; articleId: string }) =>
      api.deleteNote(noteId),
    onSuccess: (_, { articleId }) => {
      queryClient.invalidateQueries({ queryKey: ["notes", articleId] });
      queryClient.invalidateQueries({ queryKey: ["article", articleId] });
      toast.success("Note deleted");
    },
    onError: (error: Error) => {
      toast.error(`Failed to delete note: ${error.message}`);
    },
  });
}
