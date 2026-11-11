import { expect, test } from 'claude-code/testing'

const PANE = {
  plugin: 'n8nview',
  component: 'Pane',
  requestId: 'n8nview',
  props: {
    title: 'n8n execution',
    isFocused: false,
    bodyColumns: 90,
    placement: 'dock',
    scroll: { offset: 0, bodyRows: 30 },
    view: {},
  },
} as const

const RUNNING = JSON.stringify({"version": 1, "title": "Order pipeline · 7 nodes · execution 7 · running", "lines": [[{"text": "┌───────────┐", "style": "class:ok"}, {"text": " ", "style": "default"}, {"text": "┌─────────────┐", "style": "class:running"}], [{"text": "│", "style": "class:ok"}, {"text": " ", "style": "default"}, {"text": "New order", "style": "class:ok:text"}, {"text": " ", "style": "default"}, {"text": "├", "style": "class:ok"}, {"text": "►", "style": "arrow"}, {"text": "│", "style": "class:running"}, {"text": " ", "style": "default"}, {"text": "Check stock", "style": "class:running:text"}, {"text": " ", "style": "default"}, {"text": "│", "style": "class:running"}], [{"text": "│", "style": "class:ok"}, {"text": "  ", "style": "default"}, {"text": "● 0ms", "style": "class:ok:text"}, {"text": "    ", "style": "default"}, {"text": "│", "style": "class:running"}, {"text": "  ", "style": "default"}, {"text": "▶ running", "style": "class:running:text"}, {"text": "  ", "style": "default"}, {"text": "│", "style": "class:running"}]]})

test('a running execution opens the pane and is drawn in it', async ($, on) => {
  const opened: string[] = []
  on('command.register', () => ({ value: { command: 'n8nview' } }))
  on('ui.open', (_, e) => {
    opened.push(e.id)

    return { value: { isPlaced: true } }
  })
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('clock.every', () => ({ value: {} }))
  on('process.run', () => ({
    value: {
      exitCode: 0,
      stdout: RUNNING + '\n',
      stderr: '',
      isStdoutTruncated: false,
      isStderrTruncated: false,
    },
  }))

  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  expect(opened).toEqual(['n8nview'])

  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /execution 7/ }))?.text).toBe(
    'Order pipeline · 7 nodes · execution 7 · running',
  )
  const running = await ui.find({ type: 'Text', text: /^▶ running$/ })
  expect(running?.props.color).toBe('warning')
  const done = await ui.find({ type: 'Text', text: /^● 0ms$/ })
  expect(done?.props.color).toBe('success')
  await ui.unmount()
})

test('a problem from n8nview is shown instead of a drawing', async ($, on) => {
  const opened: string[] = []
  on('command.register', () => ({ value: { command: 'n8nview' } }))
  on('ui.open', (_, e) => {
    opened.push(e.id)

    return { value: { isPlaced: true } }
  })
  on('session.start', (_, e) => ({ cwd: e.cwd }))
  on('clock.every', () => ({ value: {} }))
  on('process.run', () => ({
    value: {
      exitCode: 1,
      stdout: '',
      stderr: 'n8nview: error: cannot reach n8n at http://localhost:5678\n',
      isStdoutTruncated: false,
      isStderrTruncated: false,
    },
  }))

  await $.session.start({ cwd: '/', surface: 'terminal', isInteractive: true })
  expect(opened).toEqual([])

  const ui = await $.ui.mount({ ...PANE, surface: 'terminal' })
  expect((await ui.find({ type: 'Text', text: /cannot reach/ }))?.text).toBe(
    'n8nview: error: cannot reach n8n at http://localhost:5678',
  )
  await ui.unmount()
})
