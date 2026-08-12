import test from 'node:test'
import assert from 'node:assert/strict'
import React from 'react'
import { renderToString } from 'react-dom/server'
import toast, { Toaster } from 'react-hot-toast'

import { apiErrorMessage } from '../src/lib/api-error.ts'


test('FastAPI validation detail is converted to render-safe text', () => {
  const error = {
    response: {
      data: {
        detail: [{
          type: 'value_error',
          loc: ['body', 'admin_email'],
          msg: 'value is not a valid email address',
          input: 'admin',
          ctx: { reason: 'invalid email' },
        }],
      },
    },
  }

  const message = apiErrorMessage(error, 'Setup awal gagal')

  assert.equal(typeof message, 'string')
  assert.match(message, /admin_email/)
  assert.match(message, /valid email/)
  toast.error(message)
  assert.doesNotThrow(() => renderToString(React.createElement(Toaster)))
})


test('string detail and ordinary Error remain readable', () => {
  assert.equal(
    apiErrorMessage({ response: { data: { detail: 'Bootstrap secret tidak valid' } } }, 'Gagal'),
    'Bootstrap secret tidak valid',
  )
  assert.equal(apiErrorMessage(new Error('Network Error'), 'Gagal'), 'Network Error')
  assert.equal(apiErrorMessage({}, 'Gagal'), 'Gagal')
})
