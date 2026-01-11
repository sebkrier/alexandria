import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "@/lib/api";
import { useStore } from "@/lib/store";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import toast from "react-hot-toast";

export function useCheckSetup() {
  return useQuery({
    queryKey: ["check-setup"],
    queryFn: () => api.checkSetup(),
  });
}

export function useCurrentUser() {
  const setUser = useStore((s) => s.setUser);

  const query = useQuery({
    queryKey: ["me"],
    queryFn: () => api.getMe(),
    retry: false,
  });

  useEffect(() => {
    if (query.data) {
      setUser(query.data);
    }
  }, [query.data, setUser]);

  return query;
}

export function useSetup() {
  const router = useRouter();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      api.setup(email, password),
    onSuccess: async () => {
      toast.success("Account created! Please log in.");
      queryClient.invalidateQueries({ queryKey: ["check-setup"] });
      router.push("/login");
    },
    onError: (error: Error) => {
      toast.error(`Setup failed: ${error.message}`);
    },
  });
}

export function useLogin() {
  const router = useRouter();
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: ({ email, password }: { email: string; password: string }) =>
      api.login({ email, password }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["me"] });
      toast.success("Welcome back!");
      router.push("/");
    },
    onError: () => {
      toast.error("Invalid email or password");
    },
  });
}

export function useLogout() {
  const router = useRouter();
  const setUser = useStore((s) => s.setUser);
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: () => api.logout(),
    onSuccess: () => {
      setUser(null);
      queryClient.clear();
      router.push("/login");
    },
  });
}
