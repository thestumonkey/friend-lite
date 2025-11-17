import type { Request, Response } from "express";

export async function rootHandler(_req: Request, res: Response) {
  res.json({
    message: "Mycelia API is running 🍄",
  });
}

export async function healthHandler(_req: Request, res: Response) {
  res.json({
    status: "ok",
    timestamp: new Date().toISOString(),
  });
}
