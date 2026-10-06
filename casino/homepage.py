"""Textual homepage for Terminal Casino.

Players enter their name, then pick a game from clickable buttons. Choosing a
game exits Textual so the original terminal UI for that game can run. Theme
selection is left for a later pass.
"""

from textual.app import App, ComposeResult
from textual.containers import Grid, Horizontal, Vertical
from textual.screen import Screen
from textual.widgets import Button, Footer, Header, Input, Static

# Same banner the in-game terminal UI prints above each table.
TERMINAL_CASINO_HEADER = """\
┌──────────────────────────────────────┐
│   ♦ T E R M I N A L  C A S I N O ♦   │
└──────────────────────────────────────┘"""


def game_button_label(game_key: str) -> str:
    """Display label for a game key stored in GAME_HANDLERS."""
    return game_key.title()


class NameScreen(Screen[str | None]):
    """Collect the player's name before they can sit down at a game."""

    TITLE = "Terminal Casino"

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(TERMINAL_CASINO_HEADER, id="banner")
        yield Static("Enter your name to take a seat.", id="prompt")
        with Vertical(id="name-wrap"):
            with Vertical(id="name-column"):
                yield Input(placeholder="Your name", id="name-input")
                with Horizontal(id="actions"):
                    yield Button("Continue", id="continue", variant="success")
                    yield Button("Quit", id="quit", variant="error")
        yield Footer()

    def on_mount(self) -> None:
        name_input = self.query_one("#name-input", Input)
        if self.app.player_name:
            name_input.value = self.app.player_name
            name_input.cursor_position = len(self.app.player_name)
        name_input.focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        self._submit_name(event.value)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "quit":
            self.app.exit(None)
            return
        if event.button.id == "continue":
            self._submit_name(self.query_one("#name-input", Input).value)

    def _submit_name(self, raw_name: str) -> None:
        name = raw_name.strip()
        if not name:
            self.notify("Please enter your name.", severity="error", title="Name required")
            return
        self.dismiss(name)


class GameSelectScreen(Screen[str | None]):
    """Clickable game list. Dismisses with a game key, or None to change name."""

    TITLE = "Terminal Casino"

    def __init__(self, games: list[str], player_name: str) -> None:
        super().__init__()
        self._games = games
        self._player_name = player_name

    def compose(self) -> ComposeResult:
        yield Header()
        yield Static(TERMINAL_CASINO_HEADER, id="banner")
        # markup=False so a player name cannot be read as Rich markup.
        yield Static(
            f"Welcome, {self._player_name}. Choose a game.",
            id="welcome",
            markup=False,
        )
        with Vertical(id="games-wrap"):
            with Grid(id="games"):
                for index, game in enumerate(self._games):
                    yield Button(
                        game_button_label(game),
                        id=f"game-{index}",
                        name=game,
                        classes="game-button",
                        variant="primary",
                        compact=True,
                    )
            with Horizontal(id="actions"):
                yield Button("Change Name", id="change-name", compact=True)
                yield Button("Quit", id="quit", variant="error", compact=True)
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        button_id = event.button.id
        if button_id == "quit":
            self.app.exit(None)
            return
        if button_id == "change-name":
            self.dismiss(None)
            return
        if not self._player_name.strip():
            self.notify("Please enter your name.", severity="error", title="Name required")
            return
        game = event.button.name
        if game:
            # Dismiss with the game key. The app then exits Textual so the
            # original terminal UI for that game can take over the screen.
            self.dismiss(game)


class HomepageApp(App[str | None]):
    """Lobby that returns the chosen game key, or None when the player quits."""

    TITLE = "Terminal Casino"
    CSS_PATH = "homepage.tcss"
    ENABLE_COMMAND_PALETTE = False

    def __init__(self, games: list[str], player_name: str = "") -> None:
        super().__init__()
        self.games = list(games)
        self.player_name = player_name

    def on_mount(self) -> None:
        if self.player_name.strip():
            self.push_screen(self._game_screen(), self._on_game)
        else:
            self.push_screen(NameScreen(), self._on_name)

    def _game_screen(self) -> GameSelectScreen:
        return GameSelectScreen(self.games, self.player_name)

    def _on_name(self, name: str | None) -> None:
        if not name:
            self.exit(None)
            return
        self.player_name = name
        self.push_screen(self._game_screen(), self._on_game)

    def _on_game(self, game: str | None) -> None:
        if game is None:
            self.push_screen(NameScreen(), self._on_name)
            return
        self.exit(game)


def prompt_homepage(games: list[str], player_name: str = "") -> tuple[str, str | None]:
    """Open the homepage and wait for a game choice.

    Returns the confirmed player name and the selected game key. The game key
    is None when the player quits without choosing a game.
    """
    app = HomepageApp(games=games, player_name=player_name)
    selected = app.run()
    confirmed_name = app.player_name.strip()
    if not isinstance(selected, str) or not selected:
        return confirmed_name, None
    return confirmed_name, selected
