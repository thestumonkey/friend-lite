import type { Express } from "express";
import { healthHandler, rootHandler } from "@/routes/health.ts";
import { dataAudioHandler } from "@/routes/data.audio.ts";
import { dataAudioItemsHandler } from "@/routes/data.audio.items.ts";
import { apiResourceHandler } from "@/routes/api.resource.$name.ts";
import { apiFilesIdHandler } from "@/routes/api.files.$id.ts";
import { apiFilesUploadHandler } from "@/routes/api.files.upload.ts";
import { mcpGetHandler, mcpPostHandler } from "@/routes/mcp.ts";
import { llmChatCompletionsHandler } from "@/routes/llm.chat.completions.ts";
import { oauthTokenHandler } from "@/routes/oauth.token.ts";
import { authJwtLoginHandler } from "@/routes/auth.jwt.login.ts";
import { wellKnownOauthAuthorizationServerHandler } from "@/routes/[.]well-known.oauth-authorization-server.ts";
import { wellKnownOauthProtectedResourceHandler } from "@/routes/[.]well-known.oauth-protected-resource.ts";
import { asyncHandler } from "@/middleware/asyncHandler.ts";

export function registerRoutes(app: Express): void {
  app.get("/", rootHandler);
  app.get("/health", healthHandler);
  app.get("/data/audio", dataAudioHandler);
  app.get("/data/audio/items", dataAudioItemsHandler);
  app.post("/api/resource/:name", asyncHandler(apiResourceHandler));
  app.get("/api/files/:id", apiFilesIdHandler);
  app.post("/api/files/upload", apiFilesUploadHandler);
  app.get("/mcp", mcpGetHandler);
  app.post("/mcp", mcpPostHandler);
  app.post("/llm/chat/completions", llmChatCompletionsHandler);
  app.post("/oauth/token", oauthTokenHandler);
  app.post("/auth/jwt/login", authJwtLoginHandler);
  app.get(
    "/.well-known/oauth-authorization-server",
    wellKnownOauthAuthorizationServerHandler,
  );
  app.get(
    "/.well-known/oauth-protected-resource",
    wellKnownOauthProtectedResourceHandler,
  );
}
