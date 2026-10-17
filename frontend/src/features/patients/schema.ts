import { z } from 'zod'

/** Validation for the patient registration form (mirrors backend PatientCreate). */
export const patientFormSchema = z.object({
  name: z.string().trim().min(1, 'Name is required').max(120),
  date_of_birth: z
    .string()
    .min(1, 'Date of birth is required')
    .refine((v) => !Number.isNaN(Date.parse(v)), 'Enter a valid date')
    .refine((v) => Date.parse(v) <= Date.now(), 'Date of birth cannot be in the future'),
  sex: z.string().min(1, 'Select a sex'),
  contact: z.string().trim().max(120).optional().or(z.literal('')),
})

export type PatientFormValues = z.infer<typeof patientFormSchema>
