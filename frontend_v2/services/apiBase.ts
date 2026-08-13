/**
 * apiBase — single source of truth for the backend URL.
 *
 * Resolution order:
 *   1. NEXT_PUBLIC_API_V2_URL when set. This is how local development and real
 *      deployments (Vercel etc.) configure the backend; frontend_v2/.env.local
 *      points it at http://127.0.0.1:3001.
 *   2. The hosted production backend, when the page is served from a remote host.
 *      Cloud IDEs (StackBlitz/WebContainer, CodeSandbox) strip .env files when
 *      importing from GitHub, so the env var is simply absent there — and a
 *      localhost default would make the browser call the *viewer's own machine*,
 *      which fails with "Failed to fetch".
 *   3. Localhost, for local development without an .env.local.
 *
 * Note this is evaluated in the browser bundle, so window.location reflects
 * where the page is actually being viewed from. All data fetching is
 * client-side, so the SSR branch below is only hit during build/prerender.
 */

const HOSTED_API = "https://insurance-poc-v2-backend-latest.onrender.com";
const LOCAL_API = "http://127.0.0.1:3001";

function resolveApiBase(): string {
  const fromEnv = typeof process !== "undefined" && process.env.NEXT_PUBLIC_API_V2_URL;
  if (fromEnv) return fromEnv;

  // No window during SSR/prerender; nothing fetches there, so either is safe.
  if (typeof window === "undefined") return LOCAL_API;

  const host = window.location.hostname;
  const isLocal = host === "localhost" || host === "127.0.0.1" || host === "::1" || host === "[::1]";
  return isLocal ? LOCAL_API : HOSTED_API;
}

export const API_BASE: string = resolveApiBase();
