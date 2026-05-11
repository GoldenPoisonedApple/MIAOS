import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../api/client";

export const useTasks = () => {
  const queryClient = useQueryClient();

  const { data: tasks = [], isLoading, error } = useQuery({
    queryKey: ["tasks"],
    queryFn: async () => {
      const { data, error, response } = await apiClient.GET("/api/tasks");
      if (error !== undefined) {
        const serverError = error as { message?: string; detail?: string };
        const errorMessage = serverError?.message || serverError?.detail || `エラー (${response.status} ${response.statusText})`;
        throw new Error(errorMessage);
      }
      return data || [];
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      const { error, response } = await apiClient.DELETE("/api/tasks/{id}", {
        params: { path: { id } },
      });
      if (error !== undefined) {
        const serverError = error as { message?: string; detail?: string };
        const errorMessage = serverError?.message || serverError?.detail || `削除エラー (${response.status} ${response.statusText})`;
        throw new Error(errorMessage);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tasks"] });
    },
    onError: (err) => {
      console.error(err);
      alert(err instanceof Error ? err.message : "Failed to delete task");
    },
  });

  return {
    tasks,
    loading: isLoading,
    error,
    deleteTask: (id: string) => deleteMutation.mutate(id),
    refetch: () => queryClient.invalidateQueries({ queryKey: ["tasks"] }),
  };
};
