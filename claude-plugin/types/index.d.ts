/** A run of characters that share one style, as `n8nview --format styled-json` prints it. */
export type Chunk = { text: string; style: string }

export type Frame = {
  /** The line above the drawing, or what went wrong when `isProblem`. */
  title: string
  /** The drawing, one list of chunks per line. Empty when `isProblem`. */
  lines: Chunk[][]
  /** True when n8nview could not show an execution and `title` says why. */
  isProblem: boolean
}

declare module 'claude-code' {
  interface PluginState {
    n8nview: { frame: Shaped<Frame> }
  }
}
