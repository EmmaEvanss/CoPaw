import { buildAuthHeaders } from "@/api/authHeaders";

export interface SuggestionsRequest {
  sessionId: string;
}

export interface QAContentResponse {
  success: boolean;
  qa_content?: {
    user_message: string;
    assistant_response: string;
  };
}

interface SuggestionsResponse {
  suggestions?: Array<{
    id?: string;
    suggestions?: unknown;
  }>;
}

function normalizeSuggestions(value: unknown): string[] {
  if (!Array.isArray(value)) {
    return [];
  }

  return value
    .filter((item): item is string => typeof item === "string")
    .map((item) => item.trim())
    .filter(Boolean);
}

export async function fetchSuggestions(
  request: SuggestionsRequest,
): Promise<string[]> {
  try {
    const baseUrl = window.__env__.baseUrl || "";
    const apiUrl = `${baseUrl}/api/console/suggestions?session_id=${encodeURIComponent(request.sessionId)}`;

    const response = await fetch(apiUrl, {
      method: "GET",
      headers: {
        ...buildAuthHeaders(),
      },
    });

    if (!response.ok) {
      console.error("[Suggestions] API request failed:", response.status);
      return [];
    }

    const result: SuggestionsResponse = await response.json();
    const firstEntry = Array.isArray(result.suggestions)
      ? result.suggestions[0]
      : undefined;
    return normalizeSuggestions(firstEntry?.suggestions);
  } catch (error) {
    console.error("[Suggestions] API request error:", error);
    return [];
  }
}
