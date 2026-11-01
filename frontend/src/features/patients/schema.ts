import { z } from 'zod'

import { clinicToday } from '../../lib/time'

export const BLOOD_GROUPS = ['A+', 'A-', 'B+', 'B-', 'AB+', 'AB-', 'O+', 'O-'] as const

const optionalText = (max: number) => z.string().trim().max(max).optional().or(z.literal(''))

/** Validation for the patient registration form (mirrors backend PatientCreate). */
export const patientFormSchema = z.object({
  name: z.string().trim().min(1, 'Name is required').max(120),
  date_of_birth: z
    .string()
    .min(1, 'Date of birth is required')
    .refine((v) => !Number.isNaN(Date.parse(v)), 'Enter a valid date')
    .refine((v) => v <= clinicToday(), 'Date of birth cannot be in the future'),
  sex: z.string().min(1, 'Select a sex'),
  blood_group: z.string().optional().or(z.literal('')),
  contact: optionalText(120),
  city: optionalText(80),
  emergency_contact: optionalText(160),
  notes: optionalText(500),
})

export type PatientFormValues = z.infer<typeof patientFormSchema>
