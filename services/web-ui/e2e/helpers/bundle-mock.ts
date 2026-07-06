/** E2E モック用の簡易バンドル形式(JSON)。実 pmdf.tar.gz の代わりに Playwright route で往復する。 */
export interface MockBundlePayload {
  version: 1;
  entities: Record<string, unknown>[];
  attachments: Record<string, string>;
  sanitized: boolean;
}

export const MASKED = "***MASKED***";

export function buildBundlePayload(
  entitiesByKind: Record<string, Record<string, Record<string, unknown>>>,
  options: { sanitize?: boolean } = {},
): MockBundlePayload {
  const entities: Record<string, unknown>[] = [];
  const attachments: Record<string, string> = {};

  for (const kindMap of Object.values(entitiesByKind)) {
    for (const entity of Object.values(kindMap)) {
      const copy = structuredClone(entity);
      if (options.sanitize) {
        applySanitizeProfile(copy);
      }
      entities.push(copy);
      if (Array.isArray(copy.attachments)) {
        for (const att of copy.attachments as Array<{ path?: string; sha256?: string }>) {
          if (att.path && att.sha256 && copy.id) {
            attachments[`${copy.id}/${att.path}`] = att.sha256;
          }
        }
      }
    }
  }

  return { version: 1, entities, attachments, sanitized: Boolean(options.sanitize) };
}

function setPath(obj: Record<string, unknown>, path: string, value: unknown): void {
  const keys = path.split(".");
  let current: Record<string, unknown> = obj;
  for (let i = 0; i < keys.length - 1; i += 1) {
    const key = keys[i];
    const next = current[key];
    if (typeof next !== "object" || next === null) {
      return;
    }
    current = next as Record<string, unknown>;
  }
  current[keys[keys.length - 1]] = value;
}

/** partner-share-default 相当のマスキング。 */
export function applySanitizeProfile(entity: Record<string, unknown>): void {
  const kind = String(entity.kind ?? "");
  if (kind === "story") {
    setPath(entity, "priority.reach", MASKED);
    setPath(entity, "provenance.created_by", MASKED);
  }
  if (kind === "metric") {
    setPath(entity, "current_value", MASKED);
  }
  if (kind === "stakeholder") {
    setPath(entity, "name", MASKED);
    setPath(entity, "contact_policy.personal_name", MASKED);
  }
}

export function encodeBundle(payload: MockBundlePayload): Buffer {
  return Buffer.from(JSON.stringify(payload), "utf-8");
}

export function decodeBundle(data: Buffer): MockBundlePayload {
  return JSON.parse(data.toString("utf-8")) as MockBundlePayload;
}

export function extractMultipartFile(
  postData: Buffer | null,
  contentType: string | undefined,
): Buffer | null {
  if (!postData || !contentType) {
    return null;
  }
  const boundaryMatch = contentType.match(/boundary=(.+)/);
  if (!boundaryMatch) {
    return null;
  }
  const boundary = boundaryMatch[1];
  const text = postData.toString("binary");
  for (const part of text.split(`--${boundary}`)) {
    if (!part.includes('name="file"')) {
      continue;
    }
    const headerEnd = part.indexOf("\r\n\r\n");
    if (headerEnd < 0) {
      continue;
    }
    let body = part.slice(headerEnd + 4);
    if (body.endsWith("\r\n")) {
      body = body.slice(0, -2);
    }
    return Buffer.from(body, "binary");
  }
  return null;
}

export function extractBundleBytesFromMultipart(
  postData: Buffer | null,
  contentType: string | undefined,
): Buffer | null {
  if (!postData) {
    return null;
  }
  const fromPart = extractMultipartFile(postData, contentType);
  if (fromPart && fromPart.length > 0) {
    return fromPart;
  }
  const text = postData.toString("utf-8");
  const start = text.indexOf('{"version"');
  if (start < 0) {
    return null;
  }
  const end = text.lastIndexOf("}");
  if (end < start) {
    return null;
  }
  return Buffer.from(text.slice(start, end + 1), "utf-8");
}

export function entitiesMatch(
  left: Record<string, unknown>,
  right: Record<string, unknown>,
): boolean {
  return JSON.stringify(left) === JSON.stringify(right);
}
