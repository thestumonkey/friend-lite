import type { Express, Request, Response } from "express";

export function registerHealthRoute(app: Express): void {
  app.get("/", async (_req: Request, res: Response) => {
    res.json({
      message: "Mycelia API is running 🍄",
    });
  });

  app.get("/health", async (_req: Request, res: Response) => {
    res.json({
      status: "ok",
      timestamp: new Date().toISOString(),
    });
  });
}
