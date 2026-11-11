import { atom, read, update } from 'claude-code'
import type { Color, Engine, Register } from 'claude-code'

import type { Chunk, Frame } from '../types'

const PANE = 'n8nview'
const TITLE = 'n8n execution'
const POLL_MS = 1000
const WAITING: Frame = { title: 'Waiting for n8nview…', lines: [], isProblem: true }

// The state of a node is the Mermaid class n8nview gives it. Theme colours,
// so the pane follows the person's own light or dark theme.
const STATE_COLORS: Record<string, Color> = {
  ok: 'success',
  running: 'warning',
  failed: 'error',
  idle: 'inactive',
  disabled: 'inactive',
}

const frame = atom({ plugin: 'n8nview', key: 'frame' } as const, WAITING, {
  shape: 'frame-2',
})

export const register: Register = on => {
  // The pane's width in columns, known once it has drawn; n8nview fits to it.
  let columns = 100
  // The execution the pane was last opened for, so each run opens it once.
  let openedFor = ''

  on('session.start', async ($, e, next) => {
    await $.command.register({
      name: 'n8nview',
      description: 'Show the latest n8n execution in a pane',
    })

    const poll = async () => {
      const fresh = await latest($, columns)
      await update($, frame, shown =>
        JSON.stringify(shown) === JSON.stringify(fresh) ? shown : fresh,
      )
      if (
        !fresh.isProblem &&
        fresh.title.endsWith('· running') &&
        fresh.title !== openedFor
      ) {
        openedFor = fresh.title
        void $.ui.open({ id: PANE, title: TITLE })
      }
    }
    await poll()
    $.clock.every(POLL_MS, poll)

    return next(e)
  })

  on('command.run', { command: 'n8nview' }, async $ => {
    await $.ui.open({ id: PANE, title: TITLE })

    return { text: 'n8n execution pane opened.' }
  })

  on('ui.render', { component: 'Pane', requestId: PANE }, async ($, e) => {
    const { Box, Text } = $.ui.resolve(e)
    columns = Math.max(40, e.props.bodyColumns - 1)
    const shown = await read($, frame)

    return (
      <Box flexDirection="column">
        <Text bold={!shown.isProblem} dimColor={shown.isProblem}>
          {shown.title}
        </Text>
        <Text> </Text>
        {shown.lines.map(line => (
          <Text wrap="truncate-end">
            {line.length === 0 ? ' ' : line.map(chunk => paint(Text, chunk))}
          </Text>
        ))}
      </Box>
    )
  })
}

// A style is `class:<state>` on a node's border and `class:<state>:text` on its
// label; edges, arrows and edge labels have styles of their own.
function paint(Text: any, chunk: Chunk) {
  const [kind, state, part] = chunk.style.split(':')
  if (kind === 'class' && STATE_COLORS[state]) {
    return (
      <Text color={STATE_COLORS[state]} bold={state === 'running' && part === 'text'}>
        {chunk.text}
      </Text>
    )
  }
  if (kind === 'edge' || kind === 'arrow' || kind === 'edge_label') {
    return <Text color="subtle">{chunk.text}</Text>
  }

  return <Text>{chunk.text}</Text>
}

async function latest($: Engine, columns: number): Promise<Frame> {
  try {
    const ran = await $.process.run(
      ['n8nview', '--latest', '--format', 'styled-json', '--width', String(columns)],
      { timeoutMs: 15000 },
    )
    if (ran.exitCode === 0) {
      const document = JSON.parse(ran.stdout) as { title: string; lines: Chunk[][] }

      return { title: document.title, lines: document.lines, isProblem: false }
    }

    return {
      title: ran.stderr.trim() || `n8nview exited with ${ran.exitCode}`,
      lines: [],
      isProblem: true,
    }
  } catch {
    return {
      title: 'n8nview is not installed or too old. Run: pip install -U n8nview',
      lines: [],
      isProblem: true,
    }
  }
}
