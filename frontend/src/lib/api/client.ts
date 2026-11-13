const rawBaseUrl = process.env.NEXT_PUBLIC_API_URL || "https://aetherarchive.onrender.com"
export const API_BASE_URL = rawBaseUrl.replace(/\/+$/, "")

export class ApiError extends Error {
  status?: number
  endpoint: string
  url: string

  constructor(message: string, status?: number, endpoint: string = "", url: string = "") {
    super(message)
    this.name = "ApiError"
    this.status = status
    this.endpoint = endpoint
    this.url = url
  }
}

export async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
  
  const headers = new Headers(options.headers || {})
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json")
  }
  
  if (token) {
    headers.set("Authorization", `Bearer ${token}`)
  }

  const targetUrl = `${API_BASE_URL}${endpoint}`
  
  let response: Response
  try {
    response = await fetch(targetUrl, {
      ...options,
      headers,
    })
  } catch (err) {
    const errorStr = String(err)
    if (API_BASE_URL.includes("127.0.0.1") || API_BASE_URL.includes("localhost")) {
      throw new ApiError(
        `Unable to reach backend at ${API_BASE_URL}. If deployed, please set NEXT_PUBLIC_API_URL=https://aetherarchive.onrender.com in Render Environment Variables and trigger a rebuild.`,
        0,
        endpoint,
        targetUrl
      )
    }
    throw new ApiError(
      `Network error / Backend unreachable at ${API_BASE_URL}. Please verify backend status, CORS settings, or network connectivity. (${errorStr})`,
      0,
      endpoint,
      targetUrl
    )
  }
  
  if (!response.ok) {
    let errorMsg = ""
    try {
      const errorData = await response.json()
      errorMsg = errorData.detail || errorData.message || ""
    } catch {
      // Non-JSON error body
    }

    if (response.status === 401) {
      throw new ApiError(
        errorMsg || "Authentication failed (401). Invalid email or password.",
        401,
        endpoint,
        targetUrl
      )
    }

    if (response.status === 404) {
      throw new ApiError(
        errorMsg || `Endpoint not found (404) at ${targetUrl}. Please check backend API routes.`,
        404,
        endpoint,
        targetUrl
      )
    }

    if (response.status >= 500) {
      throw new ApiError(
        errorMsg || `Backend server error (${response.status}). Please check backend logs.`,
        response.status,
        endpoint,
        targetUrl
      )
    }

    throw new ApiError(
      errorMsg || `Request failed with status ${response.status}`,
      response.status,
      endpoint,
      targetUrl
    )
  }
  
  // Return undefined for 204 No Content
  if (response.status === 204) {
    return undefined as unknown as T
  }
  
  return response.json()
}

export async function fetchStream(endpoint: string, options: RequestInit = {}, onMessage: (data: unknown) => void): Promise<void> {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
  
  const headers = new Headers(options.headers || {})
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json")
  }
  
  if (token) {
    headers.set("Authorization", `Bearer ${token}`)
  }

  const targetUrl = `${API_BASE_URL}${endpoint}`
  
  let response: Response
  try {
    response = await fetch(targetUrl, {
      ...options,
      headers,
    })
  } catch (err) {
    const errorStr = String(err)
    throw new ApiError(
      `Failed to connect to stream at ${API_BASE_URL}. (${errorStr})`,
      0,
      endpoint,
      targetUrl
    )
  }
  
  if (!response.ok) {
    let errorMsg = ""
    try {
      const errorData = await response.json()
      errorMsg = errorData.detail || errorData.message || ""
    } catch {
      // Non-JSON error body
    }
    throw new ApiError(
      errorMsg || `Stream request failed with status ${response.status}`,
      response.status,
      endpoint,
      targetUrl
    )
  }
  
  if (!response.body) {
    throw new ApiError("No response body returned from stream endpoint", response.status, endpoint, targetUrl)
  }
  
  const reader = response.body.getReader()
  const decoder = new TextDecoder()
  let buffer = ""

  while (true) {
    const { done, value } = await reader.read()
    if (done) break
    
    buffer += decoder.decode(value, { stream: true })
    const lines = buffer.split("\n\n")
    buffer = lines.pop() || ""
    
    for (const line of lines) {
      if (line.startsWith("data: ")) {
        try {
          const data = JSON.parse(line.substring(6))
          onMessage(data)
        } catch (err) {
          console.error("Failed to parse SSE data:", line, err)
        }
      }
    }
  }
}

