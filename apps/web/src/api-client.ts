export type User = {
  id: string;
  role: string;
  full_name: string | null;
};

export type Order = {
  id: string;
  client_name: string;
  cargo_type: string;
  status: string;
  created_at: string;
  trip_id: string;
};

export type Trip = {
  id: string;
  status: string;
  track_number: string | null;
  points: { id: string; name?: string; order_index: number }[];
  cargo_units: { id: string; order_index: number; vin?: string }[];
};

export type Attachment = {
  id: string;
  kind: string;
  source: string | null;
  state: string;
  download_url?: string;
};

export type Event = {
  id: string;
  event_type_code: string;
  created_at: string;
  device_time_utc: string | null;
  lat: number | null;
  lon: number | null;
  accuracy_m: number | null;
  payload: Record<string, unknown>;
  attachments: Attachment[];
};

export class ApiError extends Error {
  readonly status: number;
  readonly traceId?: string;

  constructor(status: number, message: string, traceId?: string) {
    super(message);
    this.status = status;
    this.traceId = traceId;
  }
}

export class ApiClient {
  private readonly deviceId: string;
  private readonly fetcher: typeof fetch;
  private accessToken: string | null;

  constructor(deviceId: string, fetcher: typeof fetch = fetch, accessToken: string | null = null) {
    this.deviceId = deviceId;
    this.fetcher = fetcher;
    this.accessToken = accessToken;
  }

  setAccessToken(token: string | null): void {
    this.accessToken = token;
  }

  getAccessToken(): string {
    return this.accessToken ?? "";
  }

  private async request<T>(path: string, init: RequestInit = {}): Promise<T> {
    const response = await this.fetcher(`/api/v1${path}`, {
      ...init,
      headers: {
        "Content-Type": "application/json",
        "X-Platform": "web",
        "X-App-Version": "1.0.0",
        "X-Device-Id": this.deviceId,
        ...(this.accessToken ? { Authorization: `Bearer ${this.accessToken}` } : {}),
        ...init.headers,
      },
    });
    if (!response.ok) {
      const body = (await response.json().catch(() => ({}))) as {
        error?: string;
        trace_id?: string;
      };
      throw new ApiError(response.status, body.error ?? "Ошибка запроса", body.trace_id);
    }
    return (await response.json()) as T;
  }

  async login(phone: string, password: string): Promise<User> {
    const result = await this.request<{
      access_token: string;
      user: User;
    }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        phone,
        password,
        device: { device_id: this.deviceId, platform: "web", app_version: "1.0.0" },
      }),
    });
    this.accessToken = result.access_token;
    return result.user;
  }

  me(): Promise<User> {
    return this.request<User>("/me");
  }

  orders(): Promise<Order[]> {
    return this.request<Order[]>("/orders");
  }

  trip(id: string): Promise<Trip> {
    return this.request<Trip>(`/trips/${encodeURIComponent(id)}`);
  }

  events(id: string): Promise<Event[]> {
    return this.request<Event[]>(`/trips/${encodeURIComponent(id)}/events`);
  }
}
