import { Resource } from "@/lib/auth/resources.ts";
import { Auth } from "@/lib/auth/core.server.ts";
import { CallToolResult, Tool } from "@modelcontextprotocol/sdk/types.js";
import { zodToJsonSchema } from "zod-to-json-schema";

interface MCPToolMetadata {
  resource: Resource<any, any>;
  action?: string;
}

const toolMetadataMap = new Map<string, MCPToolMetadata>();

function buildMCPInputSchema(schema: any, excludeFields?: string[]): Tool["inputSchema"] {
  const json = zodToJsonSchema(schema) as Record<string, unknown>;

  if (json && typeof json === "object" && (json as any).type === "object") {
    if (excludeFields && excludeFields.length > 0) {
      const properties = { ...(json as any).properties };
      const required = [...((json as any).required || [])];

      for (const field of excludeFields) {
        delete properties[field];
        const reqIndex = required.indexOf(field);
        if (reqIndex > -1) {
          required.splice(reqIndex, 1);
        }
      }

      return {
        ...json,
        properties,
        required,
      } as unknown as Tool["inputSchema"];
    }

    return json as unknown as Tool["inputSchema"];
  }
  return { type: "object" } as Tool["inputSchema"];
}

function extractActionDescription(schema: any, actionValue: string): string | undefined {
  if (schema._def?.typeName === "ZodObject") {
    const shape = schema._def.shape();
    const actionField = shape.action;
    if (actionField?._def?.typeName === "ZodLiteral" && actionField._def.value === actionValue) {
      return actionField._def.description || actionField.description;
    }
  }
  return undefined;
}

export function resourceToMCPTools<Input, Output>(
  resource: Resource<Input, Output>,
): Tool[] {
  const schema = resource.schemas.request;

  if (schema.def?.typeName === "ZodDiscriminatedUnion") {
    const discriminator = schema.def.discriminator;
    const optionsMap = schema.def.optionsMap;
    const tools: Tool[] = [];

    for (const [actionValue, actionSchema] of optionsMap.entries()) {
      const toolName = `${resource.code}.${actionValue}`;
      const actionDescription = extractActionDescription(actionSchema, actionValue);

      toolMetadataMap.set(toolName, {
        resource,
        action: actionValue,
      });

      tools.push({
        name: toolName,
        description: actionDescription || actionValue,
        inputSchema: buildMCPInputSchema(actionSchema, [discriminator]),
      });
    }

    return tools;
  }

  toolMetadataMap.set(resource.code, { resource });

  return [{
    name: resource.code,
    description: resource.description,
    inputSchema: buildMCPInputSchema(schema),
  }];
}

export async function handleMCPToolCall(
  toolName: string,
  auth: Auth,
  args: unknown,
): Promise<CallToolResult> {
  const metadata = toolMetadataMap.get(toolName);

  if (!metadata) {
    return {
      content: [{
        type: "text",
        text: `Error: Tool '${toolName}' not found`,
      }],
      isError: true,
    };
  }

  try {
    let input = args;

    if (metadata.action) {
      input = {
        ...args as any,
        action: metadata.action,
      };
    }

    const parsedInput = metadata.resource.schemas.request.parse(input);
    const result = await metadata.resource.use(parsedInput, auth);

    return {
      content: [],
      structuredContent: { result },
      isError: false,
    };
  } catch (error) {
    return {
      content: [{
        type: "text",
        text: `Error: ${(error as Error).message}`,
      }],
      isError: true,
    };
  }
}

export function createMCPToolsFromResources(
  resources: Resource<any, any>[],
): Tool[] {
  toolMetadataMap.clear();
  return resources.flatMap(resourceToMCPTools);
}
