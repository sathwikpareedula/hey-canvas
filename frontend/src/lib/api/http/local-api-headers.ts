/** Headers that identify legitimate Hey Canvas browser clients to the local API guard. */

export const LOCAL_API_CLIENT_HEADER = "x-hey-canvas-client";
export const LOCAL_API_CLIENT_VALUE = "hey-canvas-local";

export function localApiClientHeaders(): Record<string, string> {
  return { [LOCAL_API_CLIENT_HEADER]: LOCAL_API_CLIENT_VALUE };
}
