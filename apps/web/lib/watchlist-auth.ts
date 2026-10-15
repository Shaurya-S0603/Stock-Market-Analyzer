/** Mint a two-minute service JWT only after verified Auth.js cookie/session. */
import { SignJWT } from "jose";
import { auth } from "@/auth";
import { backendJson, forwardJson } from "@/lib/api";

const subjectPattern = /^github:[0-9]{1,30}$/;

export function rejectCrossOriginMutation(request: Request): Response | null {
  const origin = request.headers.get("origin");
  const fetchSite = request.headers.get("sec-fetch-site");
  if ((origin && origin !== new URL(request.url).origin) ||
      (fetchSite && fetchSite !== "same-origin" && fetchSite !== "none")) {
    return Response.json({ error: "Cross-origin mutations are not allowed" }, { status: 403 });
  }
  return null;
}

export async function authenticatedWatchlistRequest(
  path: string, method = "GET", body?: string,
): Promise<Response> {
  const secret = process.env.QUANTEDGE_API_JWT_SECRET ?? "";
  if (secret.length < 32 || !process.env.AUTH_SECRET ||
      !process.env.AUTH_GITHUB_ID || !process.env.AUTH_GITHUB_SECRET) {
    return Response.json({ error: "Secure research sign-in is not configured" }, { status: 503 });
  }
  const session = await auth();
  const subject = (session?.user as { id?: string } | undefined)?.id;
  if (!subject || !subjectPattern.test(subject)) {
    return Response.json({ error: "Sign in to access saved research" }, { status: 401 });
  }
  const token = await new SignJWT({})
    .setProtectedHeader({ alg: "HS256" })
    .setSubject(subject)
    .setIssuer("quantedge-next")
    .setAudience("quantedge-api")
    .setIssuedAt()
    .setExpirationTime("2m")
    .sign(new TextEncoder().encode(secret));
  const upstream = await backendJson(path, {
    method,
    headers: {
      "authorization": "Bearer " + token,
      ...(body === undefined ? {} : { "content-type": "application/json" }),
    },
    ...(body === undefined ? {} : { body }),
  });
  return forwardJson(upstream);
}
