import { buildAuthHeaders } from "@/api/authHeaders";

export interface PostTurnValidationResult {
  id: string;
  status: "needs_confirmation" | "dismissed" | "consumed";
  completed: boolean;
  reason?: string;
  session_id: string;
  expires_at?: number;
}

interface PostTurnValidationResponse {
  result?: PostTurnValidationResult | null;
}

export async function fetchPostTurnValidation(request: {
  sessionId: string;
}): Promise<PostTurnValidationResult | null> {
  try {
    const baseUrl = window.__env__.baseUrl || "";
    const apiUrl = `${baseUrl}/api/console/post-turn-validation?session_id=${encodeURIComponent(request.sessionId)}`;

    const response = await fetch(apiUrl, {
      method: "GET",
      headers: {
        ...buildAuthHeaders(),
      },
    });

    if (!response.ok) {
      console.debug("[PostTurnValidation] API request failed:", response.status);
      return null;
    }

    const result: PostTurnValidationResponse = await response.json();
    return result.result ?? null;
  } catch (error) {
    console.debug("[PostTurnValidation] API request error:", error);
    return null;
  }
}

export async function consumePostTurnValidation(request: {
  validationId: string;
  sessionId: string;
}): Promise<PostTurnValidationResult | null> {
  try {
    const baseUrl = window.__env__.baseUrl || "";
    const apiUrl = `${baseUrl}/api/console/post-turn-validation/${encodeURIComponent(request.validationId)}/consume`;

    const response = await fetch(apiUrl, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...buildAuthHeaders(),
      },
      body: JSON.stringify({
        session_id: request.sessionId,
      }),
    });

    if (!response.ok) {
      console.debug("[PostTurnValidation] Consume failed:", response.status);
      return null;
    }

    const result: PostTurnValidationResponse = await response.json();
    return result.result ?? null;
  } catch (error) {
    console.debug("[PostTurnValidation] Consume error:", error);
    return null;
  }
}
