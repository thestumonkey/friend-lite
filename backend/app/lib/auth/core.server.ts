import { jwtVerify } from "jose";
import { permissionDenied } from "./utils.ts";
import { ObjectId } from "mongodb";
import type { Request, Response } from "express";

import {
  defaultResourceManager,
  Policy,
  Resource,
  ResourcePath,
} from "./resources.ts";
import { EJSON } from "bson";
import { verifyFriendLiteToken } from "./friend-lite-jwt.ts";

export interface APIKey {
  hashedKey: string;
  salt: string;
  owner: string;
  name: string;
  openPrefix: string;
  createdAt: Date;
  isActive: boolean;
  policies: Policy[];
  _id?: ObjectId;
}

class AccessLogger {
  async log(
    auth: Auth,
    resource: Resource<any, any>,
    actions: {
      path: ResourcePath;
      actions: string[];
    }[],
  ) {
    // Format actions for more readable output
    const actionsSummary = actions.map(a =>
      `${Array.isArray(a.path) ? a.path.join('/') : a.path}:[${a.actions.join(',')}]`
    ).join(', ');

    console.log(`[Permission Check] principal=${auth.principal} resource=${resource.code} actions={${actionsSummary}}`);
    // TODO: access log to database
  }
}

export const accessLogger = new AccessLogger();

export class Auth {
  policies: Policy[];
  principal: string;
  constructor(options: {
    policies?: Policy[];
    principal: string;
  }) {
    this.policies = options.policies || [];
    this.principal = options.principal;
  }

  getResource<Input, Output>(
    code: string,
  ): Promise<(input: Input) => Promise<Output | Response>> {
    return defaultResourceManager.getResource(code, this);
  }
}

export const verifyToken = async (token: string): Promise<null | Auth> => {
  try {
    const { payload } = await jwtVerify(
      token,
      new TextEncoder().encode(Deno.env.get("SECRET_KEY")),
    );
    if (typeof payload === "string") {
      permissionDenied();
    }
    return new Auth(EJSON.deserialize(payload));
  } catch (error) {
    // JWT failed
  }

  return null;
};

export const authenticate = async (req: Request): Promise<Auth | null> => {
  const authHeader = req.headers.authorization;

  let token: string | undefined;

  if (authHeader) {
    token = authHeader.split(" ")[1];
  }

  if (!token) {
    if ("query" in req && req.query) {
      token = (req.query as any).token as string | undefined;
    }
  }

  if (!token && req.url) {
    try {
      const url = new URL(req.url);
      token = url.searchParams.get("token") || undefined;
    } catch {
      try {
        const url = new URL(req.url, `http://${req.headers.host || "localhost"}`);
        token = url.searchParams.get("token") || undefined;
      } catch {
        token = undefined;
      }
    }
  }

  if (!token) {
    return null;
  }

  // Try Friend-Lite JWT first (uses same SECRET_KEY but creates proper Auth object with policies)
  let auth = await verifyFriendLiteToken(token);

  if (!auth) {
    // Fall back to Mycelia native token verification
    auth = await verifyToken(token);
  }

  return auth;
};

export const authenticateOr401 = async (
  req: Request,
  res: Response,
): Promise<Auth> => {
  const auth = await authenticate(req);

  if (!auth) {
    res.status(401).json({ error: "Token is missing or invalid" });
    throw new Error("Unauthorized");
  }

  return auth;
};

export const getServerAuth = async (): Promise<Auth> => {
  return new Auth({
    principal: "server",
    policies: [{ resource: "**", action: "*", effect: "allow" }],
  });
};
