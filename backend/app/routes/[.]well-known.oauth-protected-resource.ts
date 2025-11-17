import type { Express, Request, Response } from "express";
import {
  buildProtectedResourceMetadata,
  protectedResourceMetadataSchema,
} from "@/lib/auth/oauth.ts";

export function registerWellKnownOauthProtectedResourceRoute(app: Express): void {
  app.get("/.well-known/oauth-protected-resource", async (req: Request, res: Response) => {
    const origin = `${req.protocol}://${req.get("host")}`;
    const body = buildProtectedResourceMetadata(origin);
    const parsed = protectedResourceMetadataSchema.safeParse(body);
    if (!parsed.success) {
      res.status(500).send("Server configuration invalid");
      return;
    }
    res.status(200).json(parsed.data);
  });
}
