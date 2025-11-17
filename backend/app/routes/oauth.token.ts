import type { Request, Response } from "express";
import {
  extractClientCredentials,
  oauthErrorJson,
  tokenRequestSchema,
} from "@/lib/auth/oauth.ts";
import { decodeAccessToken, verifyApiKey } from "@/lib/auth/tokens.ts";

export async function oauthTokenHandler(req: Request, res: Response) {
  console.log("token request");

  const creds = await extractClientCredentials(req);

  const parsed = tokenRequestSchema.safeParse({
    grant_type: creds.grantType ?? undefined,
    client_secret: creds.clientSecret || undefined,
    client_id: creds.clientId || undefined,
  });

  if (!parsed.success) {
    res.status(400).json({ error: "invalid_request" });
    return;
  }

  const keyDoc = await verifyApiKey(creds.clientSecret);
  if (!keyDoc) {
    res.status(401).json({ error: "invalid_client" });
    return;
  }

  if (keyDoc._id?.toString() !== creds.clientId) {
    res.status(401).json({ error: "invalid_client" });
    return;
  }

  const jwt = await decodeAccessToken(creds.clientSecret, "1 day");
  if (!jwt) {
    res.status(401).json({ error: "invalid_client" });
    return;
  }

  const body = {
    access_token: jwt,
    token_type: "bearer",
    expires_in: 86400,
    scope: "*",
  };
  res.status(200).json(body);
}
