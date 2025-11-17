import type { Express, Request, Response } from "express";
import { authenticateOr401 } from "@/lib/auth/core.server.ts";
import { getLLMResource } from "@/lib/llm/resource.server.ts";

export function registerLlmChatCompletionsRoute(app: Express): void {
  app.post("/llm/chat/completions", async (req: Request, res: Response) => {
    try {
      const auth = await authenticateOr401(req, res);
      const body = req.body;

      const llmResource = await getLLMResource(auth);

      const result = await llmResource({
        action: "completions",
        ...body,
      });

      // Check if result is a streaming Response
      if (result instanceof Response) {
        // Convert Response to Express response
        const responseBody = await result.json();
        res.status(result.status).json(responseBody);
        return;
      }

      res.json(result);
    } catch (error) {
      if (error instanceof Error && error.message === "Unauthorized") {
        return; // Already sent 401 response
      }
      
      if (error instanceof Response) {
        const responseBody = await error.json();
        res.status(error.status).json(responseBody);
        return;
      }

      console.error("Error processing LLM request:", error);
      res.status(500).json({
        error: {
          message: `Processing error: ${
            error instanceof Error ? error.message : "Unknown error"
          }`,
          type: "server_error",
          code: "processing_error",
        },
      });
    }
  });
}

