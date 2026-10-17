import { zodResolver } from '@hookform/resolvers/zod'
import { useForm } from 'react-hook-form'

import { Button } from '../../components/Button'
import { Input } from '../../components/Input'
import { Select } from '../../components/Select'
import { useToast } from '../../components/Toast'
import { ApiError } from '../../lib/api'
import { useRegisterPatient } from './api'
import { patientFormSchema, type PatientFormValues } from './schema'

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
    defaultValues: { name: '', date_of_birth: '', sex: '', contact: '' },
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
      <Input label="Full name" {...register('name')} error={errors.name?.message} />
      <Input
        label="Date of birth"
        type="date"
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
        label="Contact (optional)"
        {...register('contact')}
        error={errors.contact?.message}
      />

      {errors.root ? (
        <div
          role="alert"
          className="rounded-control border border-danger/20 bg-danger/5 px-3 py-2 text-sm text-danger"
        >
          {errors.root.message}
        </div>
      ) : null}

      <Button type="submit" disabled={isSubmitting}>
        {isSubmitting ? 'Registering…' : 'Register patient'}
      </Button>
    </form>
  )
}
