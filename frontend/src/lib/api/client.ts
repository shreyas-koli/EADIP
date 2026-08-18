export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8000"

export async function fetchApi<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
  const token = typeof window !== "undefined" ? localStorage.getItem("access_token") : null
  
  const headers = new Headers(options.headers || {})
  if (!headers.has("Content-Type") && !(options.body instanceof FormData)) {
    headers.set("Content-Type", "application/json")
  }
  
  if (token) {
    headers.set("Authorization", `Bearer ${token}`)
  }
  
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  })
  
  if (!response.ok) {
    let errorMsg = "An error occurred"
    try {
      const errorData = await response.json()
      errorMsg = errorData.detail || errorMsg
    } catch {
      // Ignored
    }
    throw new Error(errorMsg)
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
  
  const response = await fetch(`${API_BASE_URL}${endpoint}`, {
    ...options,
    headers,
  })
  
  if (!response.ok) {
    let errorMsg = "An error occurred"
    try {
      const errorData = await response.json()
      errorMsg = errorData.detail || errorMsg
    } catch {
      // Ignored
    }
    throw new Error(errorMsg)
  }
  
  if (!response.body) {
    throw new Error("No response body returned from stream endpoint")
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
