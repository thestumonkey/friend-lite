import type { Request, Response } from "express";
import { authenticateOr401 } from "@/lib/auth/core.server.ts";
import { getLLMResource } from "@/lib/llm/resource.server.ts";

export async function llmChatCompletionsHandler(req: Request, res: Response) {
  try {
    const auth = await authenticateOr401(req, res);
    const body = req.body;

    const llmResource = await getLLMResource(auth);

    // Force non-streaming for now since the frontend can't handle SSE
    const requestBody = {
      ...body,
      stream: false,
    };

    const result = await llmResource({
      action: "completions",
      ...requestBody,
    });

    // Check if result is a streaming Response
    if (result instanceof Response) {
      // Set headers for streaming
      res.status(result.status);

      // Copy headers from fetch Response to Express response
      result.headers.forEach((value, key) => {
        res.setHeader(key, value);
      });

      // Stream the body
      if (result.body) {
        const reader = result.body.getReader();
        const pump = async () => {
          try {
            while (true) {
              const { done, value } = await reader.read();
              if (done) break;
              res.write(value);
            }
            res.end();
          } catch (err) {
            console.error("[LLM] Streaming error:", err);
            res.end();
          }
        };
        await pump();
      } else {
        res.end();
      }
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
}
