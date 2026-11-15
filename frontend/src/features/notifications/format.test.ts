import { describe, expect, it } from 'vitest'

import { canRetry, channelLabel, notificationLabel, notificationTone } from './format'

describe('notification formatting', () => {
  it('labels demo "sent" messages honestly', () => {
    expect(notificationLabel({ status: 'sent', provider: 'console' })).toBe('Logged (demo)')
    expect(notificationLabel({ status: 'sent', provider: 'twilio' })).toBe('Sent')
    expect(notificationLabel({ status: 'skipped', provider: 'console' })).toBe('No phone on file')
    expect(notificationLabel({ status: 'failed', provider: 'twilio' })).toBe('Failed')
  })

  it('maps status to tone and channel to a name', () => {
    expect(notificationTone('failed')).toBe('danger')
    expect(notificationTone('sent')).toBe('success')
    expect(notificationTone('skipped')).toBe('neutral')
    expect(channelLabel('whatsapp')).toBe('WhatsApp')
    expect(channelLabel('none')).toBe('—')
  })

  it('only lets failed messages with attempts left be retried', () => {
    expect(canRetry({ status: 'failed', attempts: 2 })).toBe(true)
    expect(canRetry({ status: 'failed', attempts: 5 })).toBe(false)
    expect(canRetry({ status: 'sent', attempts: 1 })).toBe(false)
  })
})
