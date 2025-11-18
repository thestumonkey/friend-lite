import type { Request, Response } from "express";
import { randomBytes } from "node:crypto";
import { getServerAuth } from "@/lib/auth/core.server.ts";
import { getRedisResource } from "@/lib/redis.ts";
import { ObjectId } from "bson";
import { withRateLimit } from "@/utils/rateLimit.ts";

const PENDING_CLIENT_PREFIX = "oauth:pending_client:";
const PENDING_CLIENT_TTL = 60 * 60; // 1 hour

interface PendingClientData {
  clientId: string;
  clientSecretHash: string;
  openPrefix: string;
  clientName: string;
  redirectUris: string[];
  createdAt: number;
}

function validateRedirectUri(uri: string): boolean {
  try {
    const url = new URL(uri);

    if (url.hostname !== "localhost" && url.hostname !== "127.0.0.1") {
      if (url.protocol !== "https:") {
        return false;
      }
    }

    if (url.hostname.includes("*")) {
      return false;
    }

    const privateIpRanges = /^(10\.|172\.(1[6-9]|2[0-9]|3[01])\.|192\.168\.)/;
    if (privateIpRanges.test(url.hostname)) {
      return false;
    }

    return true;
  } catch {
    return false;
  }
}

// OAuth 2.0 Dynamic Client Registration (RFC 7591)
export const oauthRegisterHandler = withRateLimit(
  {
    keyGenerator: (req) => `register:${req.ip || req.socket.remoteAddress || "unknown"}`,
    limit: 10,
    windowSeconds: 10 * 60,
    errorMessage: "Registration rate limit exceeded. Please try again later.",
  },
  async (req: Request, res: Response) => {
    try {
      const auth = await getServerAuth();
      const redis = await getRedisResource(auth);

    const clientMetadata = req.body || {};
    const clientName = clientMetadata.client_name ||
                      clientMetadata.software_id ||
                      "MCP Client";

    const redirectUris = clientMetadata.redirect_uris || [];

    if (!Array.isArray(redirectUris) || redirectUris.length === 0) {
      res.status(400).json({
        error: "invalid_redirect_uri",
        error_description: "At least one redirect_uri is required",
      });
      return;
    }

    const invalidUris = redirectUris.filter(uri => !validateRedirectUri(uri));
    if (invalidUris.length > 0) {
      res.status(400).json({
        error: "invalid_redirect_uri",
        error_description: `Invalid redirect URIs: ${invalidUris.join(", ")}`,
      });
      return;
    }

    const clientId = new ObjectId().toString();
    const clientSecret = randomBytes(32).toString("base64url");
    const issuedAt = Math.floor(Date.now() / 1000);

    const hash = await crypto.subtle.digest(
      "SHA-256",
      new TextEncoder().encode(clientSecret)
    ).then(buf => Array.from(new Uint8Array(buf)).map(b => b.toString(16).padStart(2, "0")).join(""));

    const pendingClient: PendingClientData = {
      clientId,
      clientSecretHash: hash,
      openPrefix: clientSecret.substring(0, 8),
      clientName,
      redirectUris,
      createdAt: issuedAt,
    };

    await redis({
      action: "set",
      key: `${PENDING_CLIENT_PREFIX}${clientId}`,
      value: JSON.stringify(pendingClient),
      ttlSeconds: PENDING_CLIENT_TTL,
    });

    res.status(201).json({
      client_id: clientId,
      client_secret: clientSecret,
      client_id_issued_at: issuedAt,
      client_secret_expires_at: 0, // 0 means never expires
      redirect_uris: redirectUris,
      // Include other requested metadata
      ...(clientMetadata.token_endpoint_auth_method && {
        token_endpoint_auth_method: clientMetadata.token_endpoint_auth_method,
      }),
      ...(clientMetadata.grant_types && { grant_types: clientMetadata.grant_types }),
      ...(clientMetadata.response_types && { response_types: clientMetadata.response_types }),
      ...(clientMetadata.client_name && { client_name: clientMetadata.client_name }),
      ...(clientMetadata.client_uri && { client_uri: clientMetadata.client_uri }),
      ...(clientMetadata.logo_uri && { logo_uri: clientMetadata.logo_uri }),
      ...(clientMetadata.scope && { scope: clientMetadata.scope }),
      ...(clientMetadata.contacts && { contacts: clientMetadata.contacts }),
      ...(clientMetadata.tos_uri && { tos_uri: clientMetadata.tos_uri }),
      ...(clientMetadata.policy_uri && { policy_uri: clientMetadata.policy_uri }),
    });
  } catch (error) {
    console.error("OAuth registration error:", error);
    res.status(400).json({
      error: "invalid_client_metadata",
      error_description: error instanceof Error ? error.message : "Unknown error",
    });
  }
  }
);

