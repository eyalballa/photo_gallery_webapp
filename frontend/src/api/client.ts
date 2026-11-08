import type { components } from "./schema";

export type WallConfig = components["schemas"]["WallConfig"];
export type PublicConfig = components["schemas"]["PublicConfig"];
export type PhotoOut = components["schemas"]["PhotoOut"];
export type PhotosResponse = components["schemas"]["PhotosResponse"];
export type LoginRequest = components["schemas"]["LoginRequest"];

export type ConfigResult = { kind: "ok"; config: WallConfig } | { kind: "unauthorized" };
export type LoginResult = "ok" | "wrong" | "rate_limited";

/** The wall's view of the backend. Components receive one, so tests can pass a fake. */
export interface WallClient {
  login(passcode: string): Promise<LoginResult>;
  /** What the passcode screen may show; no session needed. */
  publicConfig(): Promise<PublicConfig>;
  config(): Promise<ConfigResult>;
  photos(since: string | null): Promise<PhotosResponse>;
}

export class HttpError extends Error {
  constructor(readonly status: number, path: string) {
    super(`${path} → HTTP ${status}`);
  }
}

type FetchFn = (input: string, init?: RequestInit) => Promise<Response>;

// a half-open connection after a Wi-Fi drop would otherwise hang the poll loop with no offline dot
const TIMEOUT_MS = 10_000;

export class HttpWallClient implements WallClient {
  constructor(
    private readonly baseUrl = "",
    private readonly fetchFn: FetchFn = (input, init) => fetch(input, init),
  ) {}

  async login(passcode: string): Promise<LoginResult> {
    const body: LoginRequest = { passcode };
    const res = await this.fetchFn(`${this.baseUrl}/api/login`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      credentials: "same-origin",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
    if (res.ok) return "ok";
    if (res.status === 401) return "wrong";
    if (res.status === 429) return "rate_limited";
    throw new HttpError(res.status, "/api/login");
  }

  async publicConfig(): Promise<PublicConfig> {
    const res = await this.get("/api/public");
    if (!res.ok) throw new HttpError(res.status, "/api/public");
    return (await res.json()) as PublicConfig;
  }

  async config(): Promise<ConfigResult> {
    const res = await this.get("/api/config");
    if (res.status === 401) return { kind: "unauthorized" };
    if (!res.ok) throw new HttpError(res.status, "/api/config");
    return { kind: "ok", config: (await res.json()) as WallConfig };
  }

  async photos(since: string | null): Promise<PhotosResponse> {
    const path = since ? `/api/photos?since=${encodeURIComponent(since)}` : "/api/photos";
    const res = await this.get(path);
    if (!res.ok) throw new HttpError(res.status, "/api/photos");
    return (await res.json()) as PhotosResponse;
  }

  private get(path: string): Promise<Response> {
    return this.fetchFn(`${this.baseUrl}${path}`, {
      credentials: "same-origin",
      cache: "no-store",
      signal: AbortSignal.timeout(TIMEOUT_MS),
    });
  }
}
