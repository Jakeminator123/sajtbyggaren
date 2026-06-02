/**
 * Zod-scheman för auth-formulär. Client-säkra (zod är isomorft) så samma
 * validering kan användas i route handlers och i klientformulär.
 */

import { z } from "zod";

export const emailSchema = z
  .string()
  .trim()
  .min(1, "Ange din e-postadress.")
  .max(200, "E-postadressen är för lång.")
  .email("Ogiltig e-postadress.")
  .transform((value) => value.toLowerCase());

export const passwordSchema = z
  .string()
  .min(8, "Lösenordet måste vara minst 8 tecken.")
  .max(200, "Lösenordet är för långt.");

export const registerSchema = z.object({
  email: emailSchema,
  password: passwordSchema,
  name: z.string().trim().max(100, "Namnet är för långt.").optional(),
});

export const loginSchema = z.object({
  email: emailSchema,
  password: z.string().min(1, "Ange ditt lösenord.").max(200),
});

export type RegisterInput = z.infer<typeof registerSchema>;
export type LoginInput = z.infer<typeof loginSchema>;
