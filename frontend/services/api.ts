export class ApiError extends Error {
  constructor(public status: number, public code: string, message: string) { super(message); }
}

const messages: Record<string, string> = {
  LOGIN_BAD_CREDENTIALS: "The email or password is incorrect.",
  REGISTER_USER_ALREADY_EXISTS: "An account with this email already exists. Please log in.",
  REGISTER_INVALID_PASSWORD: "Use a password with 12–128 characters.",
  ACCOUNT_CONFLICT: "An account with this email already exists.",
  BUSINESS_ALREADY_EXISTS: "Your account already has a business. Open your business settings.",
  AUTH_RATE_LIMITED: "Too many attempts. Please wait before trying again.",
  CSRF_INVALID: "Your form session expired. Please try again.",
  ORIGIN_REJECTED: "This address is not configured for the app. Check APP_URL in the backend settings.",
  DESTINATION_CONFIRMATION_REQUIRED: "Confirm that the Google link opens the correct business.",
  CATEGORY_INVALID: "Please choose an available business category.",
  GENERATION_LIMIT_REACHED: "You have reached the suggestion limit for this session. You can write your own review.",
  GENERATION_IN_PROGRESS: "Suggestions are still being created. Please wait a moment.",
  REVIEW_INPUT_CHANGED: "Your answers changed. Please request suggestions again.",
  RATING_REQUIRED: "Choose a rating before creating suggestions.",
  VALIDATION_ERROR: "Check your details. Use a valid email, a 12–128 character password, and a complete HTTPS destination link where requested.",
  EMAIL_VERIFICATION_REQUIRED: "Verify your email address before publishing a business.",
};

export async function api<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers = new Headers(options.headers);
  if (options.body && !(options.body instanceof URLSearchParams)) headers.set("Content-Type", "application/json");
  if (options.method && options.method !== "GET") {
    const bootstrap = await fetch("/api/auth/csrf", { credentials: "same-origin", cache: "no-store" });
    if (!bootstrap.ok) throw new ApiError(bootstrap.status, "CSRF_UNAVAILABLE", "Could not start a secure request. Please try again.");
    headers.set("X-CSRF-Token", (await bootstrap.json()).csrf_token);
  }
  let response: Response;
  try { response = await fetch(`/api${path}`, { ...options, headers, credentials: "same-origin", cache: "no-store" }); }
  catch { throw new Error("Could not connect. Check your connection and try again."); }
  if (!response.ok) {
    const data = await response.json().catch(() => ({}));
    const code = data.error?.code || "REQUEST_FAILED";
    throw new ApiError(response.status, code, messages[code] || data.error?.message || "Something went wrong. Please try again.");
  }
  return response.status === 204 ? undefined as T : response.json();
}

export type User = { id: string; email: string };
export type Category = { id: string; name: string; attributes: { id: string; label: string }[] };
export type Business = {
  id: string; name: string; category_id: string; category_name: string;
  description: string | null; brand_tone: string; status: string;
  google_review_url: string; destination_confirmed: boolean;
  public_identifier: string; review_url: string;
};
export type PublicBusiness = {
  public_identifier: string; public_slug: string; name: string; category_name: string; brand_tone: string;
  logo_url: string | null; google_review_url: string; available: boolean;
  attributes: { id: string; label: string }[];
};
export type ReviewAttribute = { attribute_id: string; polarity: "mentioned" | "positive" | "negative" };
export type ReviewSession = {
  session_token: string; expires_at: string; business: PublicBusiness;
  input_version: number; rating: number | null; selected_attributes: ReviewAttribute[];
  customer_comment: string | null;
};
export type GenerateResponse = { generation_id: string; input_version: number; reviews: { id: string; text: string }[] };
export type SelectionResponse = { selection_id: string; final_text: string; is_edited: boolean };
