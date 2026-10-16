import axios, { AxiosError } from "axios";

export const TOKEN_KEY = "credit_token";
export const USER_KEY = "credit_user";

export function getStoredToken(): string | null {
  return sessionStorage.getItem(TOKEN_KEY);
}

export function clearStoredAuth(): void {
  sessionStorage.removeItem(TOKEN_KEY);
  sessionStorage.removeItem(USER_KEY);
}

export const api = axios.create({
  baseURL: "/",
  timeout: 30000,
});

api.interceptors.request.use((config) => {
  const token = getStoredToken();
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

api.interceptors.response.use(
  (response) => response,
  (error: AxiosError) => {
    if (error.response?.status === 401 && getStoredToken()) {
      // Token expired or invalid: clear auth state and return to the login page.
      const userType = sessionStorage.getItem(USER_KEY);
      clearStoredAuth();
      const target = userType?.includes("admin") ? "/admin/login" : "/login";
      if (!window.location.pathname.endsWith("/login")) {
        window.location.href = target;
      }
    }
    return Promise.reject(error);
  },
);

export interface ApiErrorShape {
  response?: { data?: { message?: string; detail?: string } };
  message?: string;
}

export function errorMessage(error: unknown, fallback = "操作失败"): string {
  const err = error as ApiErrorShape;
  return err.response?.data?.message || err.response?.data?.detail || err.message || fallback;
}

/** Download an authenticated file endpoint as a browser save dialog. */
export async function downloadFile(path: string, fallbackName: string): Promise<void> {
  const response = await api.get(path, { responseType: "blob" });
  const disposition = String(response.headers["content-disposition"] ?? "");
  const utf8Match = disposition.match(/filename\*=UTF-8''([^;]+)/i);
  const plainMatch = disposition.match(/filename="?([^";]+)"?/i);
  const filename = utf8Match
    ? decodeURIComponent(utf8Match[1])
    : plainMatch
      ? decodeURIComponent(plainMatch[1])
      : fallbackName;
  const url = URL.createObjectURL(response.data as Blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  document.body.removeChild(anchor);
  URL.revokeObjectURL(url);
}
