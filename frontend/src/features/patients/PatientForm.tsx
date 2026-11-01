import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'

import { Button } from '../../components/Button'
import { Input } from '../../components/Input'
import { Select } from '../../components/Select'
import { Textarea } from '../../components/Textarea'
import { useToast } from '../../components/Toast'
import { ApiError } from '../../lib/api'
import { clinicToday } from '../../lib/time'
import { useRegisterPatient } from './api'
import { BLOOD_GROUPS, patientFormSchema, type PatientFormValues } from './schema'

export function PatientForm({ onCreated }: { onCreated?: () => void }) {
  const register_mutation = useRegisterPatient()
  const { toast } = useToast()
  const {
    register,
    handleSubmit,
    reset,
    setError,
    formState: { errors, isSubmitting },
  } = useForm<PatientFormValues>({
    resolver: zodResolver(patientFormSchema),
    defaultValues: {
      name: '',
      date_of_birth: '',
      sex: '',
      blood_group: '',
      contact: '',
      city: '',
      emergency_contact: '',
      notes: '',
    },
  })

  const onSubmit = handleSubmit(async (values) => {
    try {
      await register_mutation.mutateAsync(values)
      toast({ tone: 'success', title: 'Patient registered', description: values.name })
      reset()
      onCreated?.()
    } catch (err) {
      setError('root', {
        message: err instanceof ApiError ? err.message : 'Could not register patient.',
      })
    }
  })

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-4" noValidate>
      <Input
        label="Full name"
        autoComplete="off"
        {...register('name')}
        error={errors.name?.message}
      />
      <div className="grid gap-4 sm:grid-cols-2">
        <Input
          label="Date of birth"
          type="date"
          max={clinicToday()}
          {...register('date_of_birth')}
          error={errors.date_of_birth?.message}
        />
        <Select label="Sex" error={errors.sex?.message} {...register('sex')}>
          <option value="">Select…</option>
          <option value="female">Female</option>
          <option value="male">Male</option>
          <option value="other">Other</option>
        </Select>
        <Input
          label="Mobile / email"
          placeholder="+91 98xxx xxxxx"
          {...register('contact')}
          error={errors.contact?.message}
        />
        <Select label="Blood group" {...register('blood_group')}>
          <option value="">Not known</option>
          {BLOOD_GROUPS.map((g) => (
            <option key={g} value={g}>
              {g}
            </option>
          ))}
        </Select>
        <Input label="City" {...register('city')} error={errors.city?.message} />
        <Input
          label="Emergency contact"
          placeholder="Name (relation) · phone"
          {...register('emergency_contact')}
          error={errors.emergency_contact?.message}
        />
      </div>
      <Textarea
        label="Notes (allergies, conditions, anything to know)"
        {...register('notes')}
        error={errors.notes?.message}
      />

      {errors.root ? (
        <div
          role="alert"
          className="rounded-control border border-danger/20 bg-danger/5 px-3.5 py-2.5 text-sm text-danger"
        >
          {errors.root.message}
        </div>
      ) : null}

      <div className="flex justify-end pt-1">
        <Button type="submit" loading={isSubmitting}>
          {isSubmitting ? 'Registering…' : 'Register patient'}
        </Button>
      </div>
    </form>
  )
}
