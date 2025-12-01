/**
 * Friend-Lite JWT Authentication Module
 *
 * This module provides JWT validation for Friend-Lite issued tokens, allowing
 * Mycelia to accept authentication tokens from the Friend-Lite backend.
 *
 * Friend-Lite JWT Claims:
 * - sub: User ID (MongoDB ObjectId as string)
 * - email: User email address
 * - iss: "friend-lite"
 * - aud: "friend-lite"
 * - exp: Expiration timestamp
 *
 * The JWT is signed with AUTH_SECRET_KEY which must be shared between
 * Friend-Lite and Mycelia via the JWT_SECRET environment variable.
 */

import { jwtVerify } from "jose";
import { Auth } from "./core.server.ts";
import { Policy } from "./resources.ts";

export interface FriendLiteJWTPayload {
  sub: string;        // user_id
  email: string;      // user email
  iss: string;        // "friend-lite"
  aud: string;        // "friend-lite"
  exp: number;        // expiration timestamp
}

/**
 * Verify a Friend-Lite JWT token and return Auth object
 *
 * @param token - JWT token string from Friend-Lite
 * @returns Auth object with user context, or null if invalid
 */
export const verifyFriendLiteToken = async (token: string): Promise<Auth | null> => {
  try {
    const jwtSecret = Deno.env.get("JWT_SECRET") || Deno.env.get("AUTH_SECRET_KEY");

    if (!jwtSecret) {
      console.error("JWT_SECRET or AUTH_SECRET_KEY not configured for Friend-Lite JWT validation");
      return null;
    }

    // Verify the JWT token
    // Friend-Lite uses fastapi-users which sets aud to "fastapi-users:auth"
    // and doesn't set an issuer, so we don't validate those claims
    const { payload } = await jwtVerify(
      token,
      new TextEncoder().encode(jwtSecret)
    );

    const friendLitePayload = payload as any;

    // Extract principal from either Friend-Lite JWT (sub) or OAuth token (principal/owner)
    const principal = friendLitePayload.sub || friendLitePayload.principal || friendLitePayload.owner;

    if (!principal) {
      console.error("[Friend-Lite JWT] No principal found in token payload");
      return null;
    }

    // Create Auth object with user context
    // Use user_id as principal for Mycelia's permission system
    const policies: Policy[] = [
      // Grant full access to all resources for Friend-Lite users
      // Using wildcard pattern to match any resource path
      {
        resource: "**",
        action: "*",
        effect: "allow",
      },
    ];

    const auth = new Auth({
      principal,  // user_id from Friend-Lite JWT or OAuth client
      policies,
    });

    return auth;
  } catch (error) {
    console.error("[Friend-Lite JWT] Verification failed:", error);
    return null;
  }
};

/**
 * Extract user_id from Friend-Lite JWT without full verification
 * Useful for logging and debugging
 *
 * @param token - JWT token string
 * @returns user_id or null
 */
export const extractUserIdFromToken = (token: string): string | null => {
  try {
    // Simple base64 decode of payload (not cryptographically verified)
    const parts = token.split(".");
    if (parts.length !== 3) return null;

    const payload = JSON.parse(atob(parts[1]));
    return payload.sub || null;
  } catch {
    return null;
  }
};
