import type { Express } from "express";
import { registerHealthRoute } from "@/routes/health.ts";
import { registerDataAudioRoute } from "@/routes/data.audio.ts";
import { registerDataAudioItemsRoute } from "@/routes/data.audio.items.ts";
import { registerApiResourceRoute } from "@/routes/api.resource.$name.ts";
import { registerApiFilesIdRoute } from "@/routes/api.files.$id.ts";
import { registerApiFilesUploadRoute } from "@/routes/api.files.upload.ts";
import { registerMcpRoute } from "@/routes/mcp.ts";
import { registerLlmChatCompletionsRoute } from "@/routes/llm.chat.completions.ts";
import { registerOauthTokenRoute } from "@/routes/oauth.token.ts";
import { registerAuthJwtLoginRoute } from "@/routes/auth.jwt.login.ts";
import { registerWellKnownOauthAuthorizationServerRoute } from "@/routes/[.]well-known.oauth-authorization-server.ts";
import { registerWellKnownOauthProtectedResourceRoute } from "@/routes/[.]well-known.oauth-protected-resource.ts";

export function registerRoutes(app: Express): void {
  registerHealthRoute(app);
  registerDataAudioRoute(app);
  registerDataAudioItemsRoute(app);
  registerApiResourceRoute(app);
  registerApiFilesIdRoute(app);
  registerApiFilesUploadRoute(app);
  registerMcpRoute(app);
  registerLlmChatCompletionsRoute(app);
  registerOauthTokenRoute(app);
  registerAuthJwtLoginRoute(app);
  registerWellKnownOauthAuthorizationServerRoute(app);
  registerWellKnownOauthProtectedResourceRoute(app);
}

