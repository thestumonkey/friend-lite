import type { Request, Response } from "express";
import {
  extractClientCredentials,
  oauthErrorJson,
  tokenRequestSchema,
} from "@/lib/auth/oauth.ts";
import { decodeAccessToken, verifyApiKey } from "@/lib/auth/tokens.ts";
import { exchangeAuthorizationCode, exchangeRefreshToken } from "@/routes/oauth.authorize.ts";

export async function oauthTokenHandler(req: Request, res: Response) {
  console.log("token request");

  const creds = await extractClientCredentials(req);
  const grantType = creds.grantType || req.body?.grant_type || "client_credentials";

  // Handle authorization_code grant type
  if (grantType === "authorization_code") {
    const code = req.body?.code;
    const codeVerifier = req.body?.code_verifier;
    const redirectUri = req.body?.redirect_uri;

    if (!code || !codeVerifier || !redirectUri) {
      res.status(400).json({
        error: "invalid_request",
        error_description: "code, code_verifier, and redirect_uri are required",
      });
      return;
    }

    const result = await exchangeAuthorizationCode(
      code,
      creds.clientId,
      codeVerifier,
      redirectUri,
    );

    if (!result) {
      res.status(400).json({
        error: "invalid_grant",
        error_description: "Invalid or expired authorization code",
      });
      return;
    }

    res.status(200).json({
      access_token: result.accessToken,
      refresh_token: result.refreshToken,
      token_type: "bearer",
      expires_in: result.expiresIn,
      scope: "*",
    });
    return;
  }

  // Handle refresh_token grant type
  if (grantType === "refresh_token") {
    const refreshToken = req.body?.refresh_token;

    if (!refreshToken) {
      res.status(400).json({
        error: "invalid_request",
        error_description: "refresh_token is required",
      });
      return;
    }

    const result = await exchangeRefreshToken(
      refreshToken,
      creds.clientId,
    );

    if (!result) {
      res.status(400).json({
        error: "invalid_grant",
        error_description: "Invalid or expired refresh token",
      });
      return;
    }

    res.status(200).json({
      access_token: result.accessToken,
      refresh_token: result.refreshToken,
      token_type: "bearer",
      expires_in: result.expiresIn,
      scope: "*",
    });
    return;
  }

  // Handle client_credentials grant type (existing flow)
  const parsed = tokenRequestSchema.safeParse({
    grant_type: grantType,
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
