import { describe, expect, it } from 'vitest'

import { languageName } from './fields'

describe('languageName', () => {
  it('names every language code the demo data uses, including Assamese', () => {
    // codes used by the seed: hi kn te bn pa ta mr gu ml en ur as
    const used = ['en', 'hi', 'kn', 'te', 'bn', 'pa', 'ta', 'mr', 'gu', 'ml', 'ur', 'as']
    for (const code of used) expect(languageName(code)).not.toBe(code)
    expect(languageName('as')).toBe('Assamese')
  })

  it('falls back to the raw code for one it does not know', () => {
    expect(languageName('xx')).toBe('xx')
  })
})
