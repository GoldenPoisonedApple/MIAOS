import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

export interface FilterSummary {
  id: string;
}

export interface FilterListResponse {
  filters: FilterSummary[];
}

export class FilterApiError extends Error {
  readonly status: number;

  constructor(message: string, status: number) {
    super(message);
    this.name = "FilterApiError";
    this.status = status;
  }
}

async function throwIfNotOk(response: Response, fallbackMessage: string): Promise<void> {
  if (response.ok) return;
  const text = await response.text();
  throw new FilterApiError(text || `${fallbackMessage} (${response.status})`, response.status);
}

export const useFilters = () => {
  const queryClient = useQueryClient();

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["filters"],
    queryFn: async (): Promise<FilterSummary[]> => {
      const response = await fetch("/api/filters");
      await throwIfNotOk(response, "フィルタ一覧の取得に失敗");
      const body = (await response.json()) as FilterListResponse;
      return body.filters ?? [];
    },
  });

  const uploadMutation = useMutation({
    mutationFn: async ({ id, file }: { id: string; file: File }) => {
      const formData = new FormData();
      formData.append("file", file);

      const response = await fetch(`/api/filters/${encodeURIComponent(id)}`, {
        method: "POST",
        body: formData,
      });
      await throwIfNotOk(response, "フィルタのアップロードに失敗");
      return (await response.json()) as FilterSummary;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["filters"] });
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (id: string) => {
      const response = await fetch(`/api/filters/${encodeURIComponent(id)}`, {
        method: "DELETE",
      });
      await throwIfNotOk(response, "フィルタの削除に失敗");
      return (await response.json()) as FilterSummary;
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["filters"] });
    },
  });

  return {
    filters: data ?? [],
    loading: isLoading,
    error,
    refetch,
    uploadFilter: uploadMutation.mutate,
    isUploading: uploadMutation.isPending,
    deleteFilter: deleteMutation.mutate,
    isDeleting: deleteMutation.isPending,
  };
};
