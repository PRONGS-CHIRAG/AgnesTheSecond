import { z } from "zod";

export const CHAT_SCHEMA_VERSION = "v1";

export const ChatRoleSchema = z.enum(["user", "assistant"]);
export type ChatRole = z.infer<typeof ChatRoleSchema>;

export const ChatMessageSchema = z.object({
  role: ChatRoleSchema,
  content: z.string(),
});
export type ChatMessage = z.infer<typeof ChatMessageSchema>;

export const ChatRequestSchema = z.object({
  message: z.string().min(1).max(4000),
  history: z.array(ChatMessageSchema).default([]),
});
export type ChatRequest = z.infer<typeof ChatRequestSchema>;

export const ChatStepSchema = z.object({
  tool: z.string(),
  args: z.record(z.string(), z.unknown()).default({}),
  label: z.string(),
  ok: z.boolean(),
  error: z.string().nullable().default(null),
  result_preview: z.string().default(""),
  duration_ms: z.number().int().nonnegative().default(0),
});
export type ChatStep = z.infer<typeof ChatStepSchema>;

export const ChatFinishReasonSchema = z.enum([
  "stop",
  "max_iterations",
  "error",
]);
export type ChatFinishReason = z.infer<typeof ChatFinishReasonSchema>;

export const ChatResponseSchema = z.object({
  reply: z.string(),
  steps: z.array(ChatStepSchema).default([]),
  llm_model: z.string().nullable().optional(),
  finish_reason: ChatFinishReasonSchema.default("stop"),
  schema_version: z.string().default(CHAT_SCHEMA_VERSION),
});
export type ChatResponse = z.infer<typeof ChatResponseSchema>;
