# n8nview

Draw an [n8n](https://n8n.io) workflow in the terminal, from the JSON file you get with "Download" in the n8n editor.

```sh
n8nview workflow.json             # draw the workflow
n8nview --mermaid workflow.json   # the same workflow as Mermaid text
```

An n8n workflow is a JSON file, and JSON is hard to read in a pull request, in a
terminal over SSH, or in a chat with a coding agent. n8nview shows the shape of the
workflow as text: what triggers it, where it branches, and which model, memory and
tools each AI agent uses.

![n8nview demo](docs/demo.gif)

```
$ n8nview workflow.json
Ticket triage · 10 nodes

                                                 ┌──────────────────┐     ┌──────────────────────┐
                                                 │  Create invoice  │     │  Reply in Slack 💬   │
                                               ╭►│   httpRequest    ├───┬►│        slack         │
                                               │ └──────────────────┘   │ └──────────────────────┘
                                               ├─billing                │
┌──────────────┐  ┌──────────────────┐         │                        │ ╭──────────────────────╮
│  New ticket  │  │  Route by topic  │         │                        │ (  OpenAI Chat Model   )
│   webhook    ├─►│      switch      ├────┬────┤                      ╭┄┼┄(     lmChatOpenAi     )
└──────────────┘  └──────────────────┘    │    │                      ┆ │ ╰──────────────────────╯
                                  support─┤    │                      ┆ │
                                          │    │ ┌──────────────────┐ ┆ │ ╭──────────────────────╮
                                          │  2─┤ │  Support Agent   │ ┆ │ (    Simple Memory     )
                                          ╰────┼►│      agent       ├─┼─┴┄(  memoryBufferWindow  )
                                               │ └──────────────────┘ │   ╰──────────────────────╯
                                               │                      │
                                               │ ┌──────────────────┐ │   ╭──────────────────────╮
                                               │ │   Log to sheet   │ │   (      Calculator      )
                                               ╰►│   googleSheets   │ ├┄┄┄(    toolCalculator    )
                                                 │    (disabled)    │ ┆   (                      )
                                                 └──────────────────┘ ┆   ╰──────────────────────╯
                                                                      ┆
                                                                      ┆   ╭──────────────────────╮
                                                                      ┆   (  Search "docs" [v2]  )
                                                                      ╰┄┄┄(   toolHttpRequest    )
                                                                          ╰──────────────────────╯
```

Solid arrows are the main flow. Dotted lines attach the model, memory and tools to their AI agent. The outputs of IF and Switch nodes carry their names, sticky notes are left out, and disabled nodes say so.

n8nview converts the workflow to [Mermaid](https://mermaid.js.org) and draws it with [termaid](https://github.com/fasouto/termaid).

## Install

```bash
pip install n8nview
```

Or run it without installing:

```bash
uvx n8nview workflow.json
```

## Usage

```bash
n8nview workflow.json              # draw the workflow
n8nview --mermaid workflow.json    # print the Mermaid source instead
cat workflow.json | n8nview        # read from stdin
n8nview --width 120 workflow.json  # fit to 120 columns, not the terminal width
n8nview --theme nord workflow.json # draw in colour
```

Each node shows its name and its type. When the drawing is wider than the terminal, n8nview leaves the types out, and then wraps long names.

n8nview reads files and stdin only. It never calls the n8n API.

### Colour

`--theme` draws in colour with one of termaid's themes: `default`, `terra`, `neon`, `mono`, `amber`, `phosphor`, `gruvbox`, `monokai`, `dracula`, `nord` or `solarized`. Disabled nodes are grey. Colour needs [Rich](https://rich.readthedocs.io/), which is an optional extra:

```bash
pip install "n8nview[color]"
uvx --from "n8nview[color]" n8nview --theme nord workflow.json
```

## What you can do with it

**Keep a diagram next to each workflow in Git.** GitHub draws Mermaid in Markdown, so the `--mermaid` output works in a README or a pull request description. A reviewer sees what the workflow does without importing it into n8n.

````bash
{ echo '```mermaid'; n8nview --mermaid workflow.json; echo '```'; } >> README.md
````

**Draw what you just copied.** Select nodes on the n8n canvas and copy them. The clipboard holds the same JSON as an export, without the workflow name. On macOS:

```bash
pbpaste | n8nview
```

**Show a workflow to a coding agent.** The drawing and the Mermaid are both plain text, so you can paste either into a chat, or let the agent run `n8nview` itself.

## Development

```bash
uv sync
uv run pytest
vhs docs/demo.tape   # record docs/demo.gif again
```

Unofficial, not affiliated with n8n.

## License

MIT
