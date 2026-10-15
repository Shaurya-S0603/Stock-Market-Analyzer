import { backendJson, forwardJson } from "@/lib/api";
export async function GET() {
  return forwardJson(await backendJson("/api/v1/health"));
}
