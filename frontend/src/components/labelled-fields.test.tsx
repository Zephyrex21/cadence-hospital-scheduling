import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'

import { Input } from './Input'
import { Select } from './Select'
import { Textarea } from './Textarea'

/** A label that isn't wired to its control leaves the field unnamed for screen readers and
 * makes clicking the label do nothing. It must work even when no id / name is passed. */
describe('form fields are labelled without an explicit id or name', () => {
  it('Textarea', () => {
    render(<Textarea label="Resolution note" />)
    expect(screen.getByLabelText('Resolution note')).toBeInstanceOf(HTMLTextAreaElement)
  })

  it('Input', () => {
    render(<Input label="Email" />)
    expect(screen.getByLabelText('Email')).toBeInstanceOf(HTMLInputElement)
  })

  it('Select', () => {
    render(
      <Select label="Severity">
        <option value="a">A</option>
      </Select>,
    )
    expect(screen.getByLabelText('Severity')).toBeInstanceOf(HTMLSelectElement)
  })

  it('two unnamed fields on one page do not share an id', () => {
    render(
      <>
        <Textarea label="First" />
        <Textarea label="Second" />
      </>,
    )
    expect(screen.getByLabelText('First').id).not.toBe(screen.getByLabelText('Second').id)
  })

  it('an explicit id or name still wins', () => {
    render(<Input label="Phone" name="phone" />)
    expect(screen.getByLabelText('Phone').id).toBe('phone')
  })
})
