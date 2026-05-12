import createClient from "openapi-fetch";
import type { paths } from "./schema";

export const apiClient = createClient<paths>({
  baseUrl: "/", // Viteのプロキシを使うので"/"
  headers: {
    "Content-Type": "application/json",
  },
});