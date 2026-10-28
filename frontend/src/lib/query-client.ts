import { QueryClient } from "@tanstack/react-query";

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 1000 * 60 * 5, // 5 minutes cache
        gcTime: 1000 * 60 * 30, // 30 minutes garbage collection
        refetchOnWindowFocus: false,
        retry: 3,
        retryDelay: (attemptIndex: number): number => {
          return Math.min(1000 * 2 ** attemptIndex, 30000);
        },
      },
    },
  });
}
