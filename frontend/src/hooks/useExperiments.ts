import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import type { components } from "../api/schema";

export type CreateExperimentRequest = components["schemas"]["CreateExperimentRequest"];

export const useExperiments = () => {
  const queryClient = useQueryClient();

  const { data: experiments = [], isLoading, error } = useQuery({
    queryKey: ["experiments"],
    queryFn: async () => {
      const { data, error, response } = await apiClient.GET("/api/experiments");
      if (error !== undefined) {
        const serverError = error as { message?: string; detail?: string };
        const errorMessage = serverError?.message || serverError?.detail || `エラー (${response.status} ${response.statusText})`;
        throw new Error(errorMessage);
      }
      return data || [];
    },
  });

  const createMutation = useMutation({
    mutationFn: async (req: CreateExperimentRequest) => {
      const { data, error, response } = await apiClient.POST("/api/experiments", {
        body: req,
      });
      if (error !== undefined) {
        const serverError = error as { message?: string; detail?: string };
        const errorMessage = serverError?.message || serverError?.detail || `作成エラー (${response.status} ${response.statusText})`;
        throw new Error(errorMessage);
      }
      return data;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["experiments"] });
    },
    onError: (err) => {
      console.error(err);
      alert(err instanceof Error ? err.message : "Failed to create experiment");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: number) => {
      const { error, response } = await apiClient.DELETE("/api/experiments/{id}", {
        params: { path: { id } },
      });
      if (error !== undefined) {
        const serverError = error as { message?: string; detail?: string };
        const errorMessage = serverError?.message || serverError?.detail || `削除エラー (${response.status} ${response.statusText})`;
        throw new Error(errorMessage);
      }
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["experiments"] });
    },
    onError: (err) => {
      console.error(err);
      alert(err instanceof Error ? err.message : "Failed to delete experiment");
    },
  });

  return {
    experiments,
    loading: isLoading,
    error,
    createExperiment: async (req: CreateExperimentRequest) => {
      await createMutation.mutateAsync(req);
    },
    isCreating: createMutation.isPending,
    deleteExperiment: (id: number) => deleteMutation.mutate(id),
    refetch: () => queryClient.invalidateQueries({ queryKey: ["experiments"] }),
  };
};
