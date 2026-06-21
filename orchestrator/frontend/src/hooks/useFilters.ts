import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export interface FilterSummary {
  id: string;
}

export interface FilterListResponse {
  filters: FilterSummary[];
}

export const useFilters = () => {
  const queryClient = useQueryClient();

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["filters"],
    queryFn: async (): Promise<FilterSummary[]> => {
      const response = await fetch("/api/filters");
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `フィルタ一覧の取得に失敗 (${response.status})`);
      }
      const body = (await response.json()) as FilterListResponse;
      return body.filters ?? [];
    },
  });

  const uploadMutation = useMutation({
    mutationFn: async ({ id, file }: { id: string; file: File }) => {
      const formData = new FormData();
      formData.append("id", id);
      formData.append("file", file);

      const response = await fetch("/api/filters", {
        method: "POST",
        body: formData,
      });
      if (!response.ok) {
        const text = await response.text();
        throw new Error(text || `フィルタのアップロードに失敗 (${response.status})`);
      }
      return (await response.json()) as FilterSummary;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["filters"] });
    },
    onError: (err) => {
      console.error(err);
      alert(err instanceof Error ? err.message : "フィルタのアップロードに失敗しました");
    },
  });

  return {
    filters: data ?? [],
    loading: isLoading,
    error,
    refetch,
    uploadFilter: uploadMutation.mutate,
    isUploading: uploadMutation.isPending,
  };
};
