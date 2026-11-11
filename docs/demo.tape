# Records docs/demo.gif with vhs (https://github.com/charmbracelet/vhs).
#
#   uv sync && vhs docs/demo.tape
#
# Run it from the repo root. It draws the two workflows in tests/fixtures,
# the second one in colour, and then prints the first one as Mermaid.

Output docs/demo.gif

Set Shell "bash"
Set FontSize 12
Set Width 1050
Set Height 640
Set Padding 15
Set Margin 15
Set MarginFill "#FFFFFF"
Set BorderRadius 10
Set WindowBar Colorful
Set TypingSpeed 32ms
Set Theme { "name": "Catppuccin Mocha", "black": "#1e1e2e", "red": "#f38ba8", "green": "#a6e3a1", "yellow": "#f9e2af", "blue": "#89b4fa", "magenta": "#cba6f7", "cyan": "#94e2d5", "white": "#cdd6f4", "brightBlack": "#585b70", "brightRed": "#f38ba8", "brightGreen": "#a6e3a1", "brightYellow": "#f9e2af", "brightBlue": "#89b4fa", "brightMagenta": "#cba6f7", "brightCyan": "#94e2d5", "brightWhite": "#a6adc8", "background": "#1e1e2e", "foreground": "#cdd6f4", "selection": "#585b70", "cursor": "#f5e0dc" }

Env "PS1" "$ "
Env "VIRTUAL_ENV_DISABLE_PROMPT" "1"

Hide
Type "source .venv/bin/activate && cd tests/fixtures && clear"
Enter
Show

Type "n8nview linear.json"
Enter
Sleep 4s

Ctrl+L
Type "n8nview --theme default branching.json"
Enter
Sleep 8s

Ctrl+L
Type "n8nview --mermaid linear.json"
Enter
Sleep 5s
