# Use one set of configuration for all platforms.
- settings.json (User)
  Ctrl + Shift + P -> Preferences: Open User Settings (JSON)
  - On Windows
    C:\Users\Username\AppData\Roaming\Code\User\settings.json
  - On Linux
    $HOME/.config/Code/User/settings.json
  - On Mac
    $HOME/Library/Application Support/Code/User/settings.json

- settings.json (Remote, Always a Linux)
  Ctrl + Shift + P -> Preferences: Open Remote Settings (JSON)
  - On Linux
    $HOME/.vscode-server/data/Machine/settings.json

- keybindings.json
  Ctrl + Shift + P -> Preferences: Open Keyboard Shortcuts (JSON)
  - On Windows
    C:\Users\Username\AppData\Roaming\Code\User\keybindings.json
  - On Linux
    $HOME/.config/Code/User/keybindings.json
  - On Mac
    $HOME/Library/Application Support/Code/User/keybindings.json

- workbench.desktop.main.css
  - On Windows
    C:\Users\Username\AppData\Local\Programs\Microsoft VS Code\resources\app\out\vs\workbench\workbench.desktop.main.css
  - On Linux
    $HOME/.vscode-server/data/Machine
  - On Mac
    $HOME/Library/Application Support/Code/User/workbench.desktop.main.css

- extensions.json (Remote)
  - On Linux
    $HOME/.vscode-server/extensions/extensions.json