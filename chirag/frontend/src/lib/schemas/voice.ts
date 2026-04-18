import { z } from "zod";

import { ChatStepSchema } from "@/lib/schemas/chat";

export const VoiceTimingsSchema = z.object({
  stt_ms: z.number().int().nonnegative().default(0),
  translate_ms: z.number().int().nonnegative().default(0),
  answer_ms: z.number().int().nonnegative().default(0),
  humanize_ms: z.number().int().nonnegative().default(0),
  backtranslate_ms: z.number().int().nonnegative().default(0),
  total_ms: z.number().int().nonnegative().default(0),
});
export type VoiceTimings = z.infer<typeof VoiceTimingsSchema>;

export const VoiceRespondResponseSchema = z.object({
  transcript: z.string(),
  detected_language: z.string().default(""),
  detected_language_name: z.string().default(""),
  language_probability: z.number().min(0).max(1).default(0),
  english_transcript: z.string().default(""),
  answer_raw: z.string(),
  answer_spoken_en: z.string().default(""),
  answer_spoken: z.string(),
  answer_language: z.string().default("en"),
  steps: z.array(ChatStepSchema).default([]),
  timings: VoiceTimingsSchema.default({
    stt_ms: 0,
    translate_ms: 0,
    answer_ms: 0,
    humanize_ms: 0,
    backtranslate_ms: 0,
    total_ms: 0,
  }),
  llm_model: z.string(),
  voice_id: z.string(),
  schema_version: z.string(),
});
export type VoiceRespondResponse = z.infer<typeof VoiceRespondResponseSchema>;

export const VoiceConfigSchema = z.object({
  ready: z.boolean(),
  voice_id: z.string(),
  schema_version: z.string(),
});
export type VoiceConfig = z.infer<typeof VoiceConfigSchema>;
