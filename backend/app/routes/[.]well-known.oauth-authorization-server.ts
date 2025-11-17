import type { Request, Response } from "express";
import {
  authorizationServerMetadataSchema,
  buildAuthorizationServerMetadata,
} from "@/lib/auth/oauth.ts";

export async function wellKnownOauthAuthorizationServerHandler(
  req: Request,
  res: Response,
) {
  const origin = `${req.protocol}://${req.get("host")}`;
  const body = buildAuthorizationServerMetadata(origin);
  const parsed = authorizationServerMetadataSchema.safeParse(body);
  if (!parsed.success) {
    res.status(500).send("Server configuration invalid");
    return;
  }
  res.status(200).json(parsed.data);
}
