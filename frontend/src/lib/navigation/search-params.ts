export function removeSearchParams(
  pathname: string,
  search: URLSearchParams | string,
  keys: string[],
): string {
  const params = new URLSearchParams(typeof search === "string" ? search : search.toString());
  for (const key of keys) params.delete(key);
  const qs = params.toString();
  return qs ? `${pathname}?${qs}` : pathname;
}
