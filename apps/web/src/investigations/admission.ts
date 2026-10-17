export type PendingAdmission = {
  version: 1;
  key: string;
  requestDigest: string;
  id?: string;
};
export const admissionStorageKey = "faultglass.admission.v1";
export function savedStart(): PendingAdmission | null {
  try {
    const value = JSON.parse(
      sessionStorage.getItem(admissionStorageKey) ?? "null",
    );
    return value?.version === 1 &&
      /^[a-f0-9-]{36}$/.test(value.key) &&
      /^[a-f0-9]{64}$/.test(value.requestDigest)
      ? value
      : null;
  } catch {
    return null;
  }
}
export function saveStart(value: PendingAdmission) {
  try {
    sessionStorage.setItem(admissionStorageKey, JSON.stringify(value));
  } catch {
    throw new Error(
      "We couldn’t save your start details. Allow browser storage and try again.",
    );
  }
}
export async function requestDigest(body: string) {
  const hash = await crypto.subtle.digest(
    "SHA-256",
    new TextEncoder().encode(body),
  );
  return Array.from(new Uint8Array(hash), (byte) =>
    byte.toString(16).padStart(2, "0"),
  ).join("");
}
