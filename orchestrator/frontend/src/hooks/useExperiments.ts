import { useCallback, useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { apiClient } from "../api/client";
import type { components } from "../api/schema";

export type CreateExperimentRequest = components["schemas"]["CreateExperimentRequest"];
export type Experiment = components["schemas"]["Model"];
export type ExperimentPageResponse = components["schemas"]["ExperimentPageResponse"];

const EXPERIMENTS_LIST_PAGE_KEY = "experimentsListPage";
const PAGE_LIMIT = 100;

function readStoredPage(): number | null {
  try {
    const raw = sessionStorage.getItem(EXPERIMENTS_LIST_PAGE_KEY);
    if (raw == null) return null;
    const parsed = parseInt(raw, 10);
    if (!Number.isFinite(parsed) || parsed < 1) return null;
    return parsed;
  } catch {
    return null;
  }
}

function writeStoredPage(page: number): void {
  try {
    sessionStorage.setItem(EXPERIMENTS_LIST_PAGE_KEY, String(page));
  } catch {
    // sessionStorage 不可時は握りつぶす
  }
}

/** 空ページ（総ページ超過など）のときに遷移すべきページ番号 */
function pageAfterEmptyItems(queryPage: number, total: number, limit: number): number {
  const pageMax = Math.max(1, Math.ceil(total / limit));
  const effectivePage = queryPage === 0 ? pageMax : queryPage;
  return Math.min(effectivePage, pageMax);
}

async function fetchExperimentsPage(page: number): Promise<ExperimentPageResponse> {
  const { data, error, response } = await apiClient.GET("/api/experiments", {
    params: { query: { page, limit: PAGE_LIMIT } },
  });
  if (error !== undefined) {
    const serverError = error as { message?: string; detail?: string };
    const errorMessage =
      serverError?.message ||
      serverError?.detail ||
      `エラー (${response.status} ${response.statusText})`;
    throw new Error(errorMessage);
  }
  if (!data) {
    throw new Error("実験一覧のレスポンスが空です");
  }
  return data;
}

async function fetchExperimentsPageResolved(queryPage: number): Promise<ExperimentPageResponse> {
  let result = await fetchExperimentsPage(queryPage);
  if (result.items.length === 0 && result.total > 0) {
    const next = pageAfterEmptyItems(queryPage, result.total, result.limit);
    if (next !== queryPage) {
      result = await fetchExperimentsPage(next);
    }
  }
  // sentinel(0) や総ページ超過の補正後は、次回復元用に実際のページを保存する
  if (result.page !== queryPage) {
    writeStoredPage(result.page);
  }
  return result;
}

export const useExperiments = () => {
  const queryClient = useQueryClient();
  const [page, setPageState] = useState<number | null>(() => readStoredPage());

  const queryPage = page ?? 0;

  const { data, isLoading, error, isFetching } = useQuery({
    queryKey: ["experiments", queryPage],
    queryFn: () => fetchExperimentsPageResolved(queryPage),
  });

  const setPage = useCallback((next: number) => {
    setPageState(next);
    writeStoredPage(next);
  }, []);

  const adjustPageAfterMutation = useCallback(async () => {
    const currentQueryPage = page ?? 0;
    const fresh = await queryClient.fetchQuery({
      queryKey: ["experiments", currentQueryPage],
      queryFn: () => fetchExperimentsPageResolved(currentQueryPage),
    });
    if (fresh.items.length === 0 && fresh.total > 0) {
      setPage(pageAfterEmptyItems(currentQueryPage, fresh.total, fresh.limit));
      return;
    }
    await queryClient.invalidateQueries({ queryKey: ["experiments"] });
  }, [page, queryClient, setPage]);

  const createMutation = useMutation({
    mutationFn: async (req: CreateExperimentRequest) => {
      const { data, error, response } = await apiClient.POST("/api/experiments", {
        body: req,
      });
      if (error !== undefined) {
        const serverError = error as { message?: string; detail?: string };
        const errorMessage =
          serverError?.message ||
          serverError?.detail ||
          `作成エラー (${response.status} ${response.statusText})`;
        throw new Error(errorMessage);
      }
      return data;
    },
    onSuccess: async () => {
      await adjustPageAfterMutation();
    },
    onError: (err) => {
      console.error(err);
      alert(err instanceof Error ? err.message : "Failed to create experiment");
    },
  });

  const deleteMutation = useMutation({
    mutationFn: async (ids: number[]) => {
      await Promise.all(
        ids.map(async (id) => {
          const { error, response } = await apiClient.DELETE("/api/experiments/{id}", {
            params: { path: { id } },
          });
          if (error !== undefined) {
            const serverError = error as { message?: string; detail?: string };
            const errorMessage =
              serverError?.message ||
              serverError?.detail ||
              `削除エラー (${response.status} ${response.statusText})`;
            throw new Error(errorMessage);
          }
        })
      );
    },
    onSuccess: async () => {
      await adjustPageAfterMutation();
    },
    onError: (err) => {
      console.error(err);
      alert(err instanceof Error ? err.message : "Failed to delete experiment");
    },
  });

  const rerunMutation = useMutation({
    mutationFn: async (ids: number[]) => {
      await Promise.all(
        ids.map(async (id) => {
          const { error, response } = await apiClient.POST("/api/experiments/{id}/rerun", {
            params: { path: { id } },
          });
          if (error !== undefined) {
            const serverError = error as { message?: string; detail?: string };
            const errorMessage =
              serverError?.message ||
              serverError?.detail ||
              `再実行エラー (${response.status} ${response.statusText})`;
            throw new Error(errorMessage);
          }
        })
      );
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["experiments"] });
    },
    onError: (err) => {
      console.error(err);
      alert(err instanceof Error ? err.message : "Failed to rerun experiment");
    },
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const limit = data?.limit ?? PAGE_LIMIT;
  // 総ページ超過時は queryFn 内で実ページを取り直すため、表示は API の page を優先する
  const currentPage = data?.page ?? page ?? 1;
  const pageMax = Math.max(1, Math.ceil(total / limit));

  return {
    items,
    total,
    limit,
    page: currentPage,
    pageMax,
    setPage,
    loading: isLoading,
    fetching: isFetching,
    error,
    createExperiment: async (req: CreateExperimentRequest) => {
      await createMutation.mutateAsync(req);
    },
    isCreating: createMutation.isPending,
    deleteExperiments: (ids: number[], options?: Parameters<typeof deleteMutation.mutate>[1]) =>
      deleteMutation.mutate(ids, options),
    isDeleting: deleteMutation.isPending,
    rerunExperiments: (ids: number[], options?: Parameters<typeof rerunMutation.mutate>[1]) =>
      rerunMutation.mutate(ids, options),
    isRerunning: rerunMutation.isPending,
    refetch: () => queryClient.invalidateQueries({ queryKey: ["experiments"] }),
  };
};
