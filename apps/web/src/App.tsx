import { useCallback, useEffect, useMemo, useState, type FormEvent } from "react";
import { ApiClient, ApiError, type Event, type Order, type Trip, type User } from "./api-client";

const DEVICE_KEY = "reis-control-web-device";
const TOKEN_KEY = "reis-control-web-access";

function dateTime(value: string | null | undefined): string {
  return value ? new Date(value).toLocaleString("ru-RU") : "—";
}

function errorText(error: unknown): string {
  if (error instanceof ApiError) {
    return `${error.message}${error.traceId ? ` · код ${error.traceId}` : ""}`;
  }
  return "Не удалось связаться с сервером. Проверьте соединение.";
}

function getDeviceId(): string {
  let id = localStorage.getItem(DEVICE_KEY);
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem(DEVICE_KEY, id);
  }
  return id;
}

export function App() {
  const client = useMemo(() => new ApiClient(getDeviceId()), []);
  const [user, setUser] = useState<User | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [selected, setSelected] = useState<Order | null>(null);
  const [trip, setTrip] = useState<Trip | null>(null);
  const [events, setEvents] = useState<Event[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [phone, setPhone] = useState("");
  const [password, setPassword] = useState("");

  const loadOrders = useCallback(async () => {
    setBusy(true);
    setError(null);
    try {
      setOrders(await client.orders());
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusy(false);
    }
  }, [client]);

  useEffect(() => {
    const token = sessionStorage.getItem(TOKEN_KEY);
    if (!token) return;
    client.setAccessToken(token);
    void client
      .me()
      .then((profile) => {
        if (profile.role !== "logistician" && profile.role !== "admin") {
          sessionStorage.removeItem(TOKEN_KEY);
          client.setAccessToken(null);
          setError("Для этого кабинета нужна роль логиста.");
          return;
        }
        setUser(profile);
        void loadOrders();
      })
      .catch(() => {
        sessionStorage.removeItem(TOKEN_KEY);
        client.setAccessToken(null);
      });
  }, [client, loadOrders]);

  async function submitLogin(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      const profile = await client.login(phone, password);
      if (profile.role !== "logistician" && profile.role !== "admin") {
        client.setAccessToken(null);
        setError("Для этого кабинета нужна роль логиста.");
        return;
      }
      // Login returns the token to the client; keep it for this browser session only.
      sessionStorage.setItem(TOKEN_KEY, client.getAccessToken());
      setPassword("");
      setUser(profile);
      await loadOrders();
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusy(false);
    }
  }

  async function selectOrder(order: Order) {
    setSelected(order);
    setTrip(null);
    setEvents([]);
    setBusy(true);
    setError(null);
    try {
      const [details, timeline] = await Promise.all([
        client.trip(order.trip_id),
        client.events(order.trip_id),
      ]);
      setTrip(details);
      setEvents(timeline);
    } catch (caught) {
      setError(errorText(caught));
    } finally {
      setBusy(false);
    }
  }

  function logout() {
    sessionStorage.removeItem(TOKEN_KEY);
    client.setAccessToken(null);
    setUser(null);
    setOrders([]);
    setSelected(null);
    setTrip(null);
    setEvents([]);
  }

  if (!user) {
    return (
      <main className="login-page">
        <section className="login-card">
          <p className="eyebrow">Рейс-Контроль</p>
          <h1>Кабинет логиста</h1>
          <p className="muted">Войдите, чтобы просматривать заявки и события рейсов.</p>
          <form onSubmit={(event) => void submitLogin(event)}>
            <label>
              Телефон
              <input
                autoComplete="username"
                value={phone}
                onChange={(event) => setPhone(event.target.value)}
                required
              />
            </label>
            <label>
              Пароль
              <input
                type="password"
                autoComplete="current-password"
                value={password}
                onChange={(event) => setPassword(event.target.value)}
                required
              />
            </label>
            <button type="submit" disabled={busy}>
              Войти
            </button>
          </form>
          {error && (
            <p className="error" role="alert">
              {error}
            </p>
          )}
        </section>
      </main>
    );
  }

  return (
    <div className="shell">
      <header className="topbar">
        <div>
          <p className="eyebrow">Рейс-Контроль</p>
          <h1>Кабинет логиста</h1>
        </div>
        <div className="top-actions">
          <span>{user.full_name ?? "Логист"}</span>
          <button className="secondary" onClick={logout}>
            Выйти
          </button>
        </div>
      </header>
      {error && (
        <p className="error" role="alert">
          {error}
        </p>
      )}
      <div className="columns">
        <section className="panel orders">
          <div className="section-heading">
            <h2>Заявки</h2>
            <button className="secondary" onClick={() => void loadOrders()} disabled={busy}>
              Обновить
            </button>
          </div>
          {orders.length === 0 && (
            <p className="muted">{busy ? "Загрузка…" : "Доступных заявок нет."}</p>
          )}
          <ul className="order-list">
            {orders.map((order) => (
              <li key={order.id}>
                <button
                  className={`order-card ${selected?.id === order.id ? "selected" : ""}`}
                  onClick={() => void selectOrder(order)}
                >
                  <strong>{order.client_name}</strong>
                  <span>{order.cargo_type}</span>
                  <small>
                    {order.status} · {dateTime(order.created_at)}
                  </small>
                </button>
              </li>
            ))}
          </ul>
        </section>
        <main className="panel details">
          {!selected && <p className="empty">Выберите заявку, чтобы увидеть рейс и события.</p>}
          {selected && (
            <>
              <p className="eyebrow">Заявка {selected.id}</p>
              <h2>{selected.client_name}</h2>
              {busy && <p className="muted">Загрузка рейса…</p>}
              {trip && (
                <>
                  <div className="facts">
                    <span>Рейс: {trip.track_number ?? trip.id}</span>
                    <span>Статус: {trip.status}</span>
                    <span>Точек: {trip.points.length}</span>
                    <span>Грузовых единиц: {trip.cargo_units.length}</span>
                  </div>
                  <h3>События рейса</h3>
                  {events.length === 0 && <p className="muted">Принятых событий пока нет.</p>}
                  <ol className="timeline">
                    {events.map((item) => (
                      <li key={item.id} className="event-card">
                        <div className="event-heading">
                          <strong>{item.event_type_code}</strong>
                          <time>{dateTime(item.device_time_utc ?? item.created_at)}</time>
                        </div>
                        {item.lat !== null && item.lon !== null && (
                          <p className="location">
                            Координаты: {item.lat.toFixed(6)}, {item.lon.toFixed(6)}
                            {item.accuracy_m !== null && ` · точность ${item.accuracy_m} м`}
                          </p>
                        )}
                        {item.attachments.length > 0 && (
                          <ul className="attachments">
                            {item.attachments.map((attachment) => (
                              <li key={attachment.id}>
                                {attachment.download_url ? (
                                  <a
                                    href={attachment.download_url}
                                    target="_blank"
                                    rel="noreferrer"
                                  >
                                    Открыть {attachment.kind}
                                  </a>
                                ) : (
                                  <span>{attachment.kind}</span>
                                )}
                                <small>
                                  {attachment.source ?? ""} · {attachment.state}
                                </small>
                              </li>
                            ))}
                          </ul>
                        )}
                      </li>
                    ))}
                  </ol>
                </>
              )}
            </>
          )}
        </main>
      </div>
    </div>
  );
}
