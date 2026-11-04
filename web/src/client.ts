let csrfToken = "";
let lastActivity = Date.now();
for (const event of ["pointerdown", "keydown", "scroll"]) {
  window.addEventListener(
    event,
    () => {
      lastActivity = Date.now();
    },
    { passive: true },
  );
}
export function setCsrf(value: string) {
  csrfToken = value;
}
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function api(path: string, method = "GET", data?: any) {
  const response = await fetch("/api/v1" + path, {
    method,
    credentials: "same-origin",
    headers: {
      "Content-Type": "application/json",
      ...(Date.now() - lastActivity > 60000
        ? { "X-Background-Request": "1" }
        : {}),
      ...(csrfToken ? { "X-CSRF-Token": csrfToken } : {}),
    },
    body: data === undefined ? undefined : JSON.stringify(data),
  });
  const body = await response.json();
  if (!response.ok) {
    if (response.status === 401 && !path.startsWith("/auth/login"))
      window.dispatchEvent(new Event("aptilume:unauthorized"));
    throw new ApiError(
      body.message || body.detail?.[0]?.msg || "İşlem tamamlanamadı.",
      response.status,
    );
  }
  return body;
}
