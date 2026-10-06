"""Tests for the Textual homepage and the handoff to the original game UI."""

import asyncio
from unittest.mock import Mock, patch

from textual.widgets import Input, Static

from casino.homepage import (
    TERMINAL_CASINO_HEADER,
    GameSelectScreen,
    HomepageApp,
    NameScreen,
)
from casino.main import ACCOUNT_STARTING_BALANCE, ALL_GAMES, GAME_HANDLERS, run_casino


def _run(coro):
    return asyncio.run(coro)


async def _enter_name(pilot, name: str) -> None:
    name_input = pilot.app.screen.query_one("#name-input", Input)
    name_input.value = name
    await pilot.click("#continue")
    await pilot.pause()


def test_header_and_name_are_required_before_a_game():
    async def body():
        app = HomepageApp(games=ALL_GAMES)
        async with app.run_test(size=(80, 24), notifications=True) as pilot:
            banner = pilot.app.screen.query_one("#banner", Static)
            assert "T E R M I N A L" in str(banner.content)
            assert "C A S I N O" in str(banner.content)
            assert TERMINAL_CASINO_HEADER.strip() in str(banner.content)
            assert pilot.app.title == "Terminal Casino"
            assert isinstance(pilot.app.screen, NameScreen)

            await pilot.click("#continue")
            await pilot.pause()
            assert isinstance(pilot.app.screen, NameScreen)

            # The button ignores a second press while its click animation is running.
            await pilot.pause(0.3)
            pilot.app.screen.query_one("#name-input", Input).value = "   "
            await pilot.click("#continue")
            await pilot.pause()
            assert isinstance(pilot.app.screen, NameScreen)
            assert app.return_value is None

    _run(body())


def test_name_entry_opens_every_game_button():
    async def body():
        app = HomepageApp(games=ALL_GAMES)
        async with app.run_test(size=(80, 24)) as pilot:
            await _enter_name(pilot, "Ada")
            assert isinstance(pilot.app.screen, GameSelectScreen)
            welcome = str(pilot.app.screen.query_one("#welcome", Static).content)
            assert "Ada" in welcome
            assert "T E R M I N A L" in str(pilot.app.screen.query_one("#banner", Static).content)

            game_buttons = list(pilot.app.screen.query(".game-button").results())
            assert [button.name for button in game_buttons] == ALL_GAMES
            assert [str(button.label) for button in game_buttons] == [
                name.title() for name in ALL_GAMES
            ]

    _run(body())


def test_game_button_exits_with_that_game():
    async def body(game_index: int, game_name: str):
        app = HomepageApp(games=ALL_GAMES)
        async with app.run_test(size=(80, 24)) as pilot:
            await _enter_name(pilot, "Ada")
            clicked = await pilot.click(f"#game-{game_index}")
            assert clicked
            await pilot.pause()
        assert app.player_name == "Ada"
        assert app.return_value == game_name

    for index, name in enumerate(ALL_GAMES):
        _run(body(index, name))


def test_change_name_returns_to_name_screen():
    async def body():
        app = HomepageApp(games=["slots"], player_name="Ada")
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            assert isinstance(pilot.app.screen, GameSelectScreen)
            await pilot.click("#change-name")
            await pilot.pause()
            assert isinstance(pilot.app.screen, NameScreen)
            assert pilot.app.screen.query_one("#name-input", Input).value == "Ada"

            await _enter_name(pilot, "Grace")
            assert isinstance(pilot.app.screen, GameSelectScreen)
            welcome = str(pilot.app.screen.query_one("#welcome", Static).content)
            assert "Grace" in welcome

    _run(body())


def test_quit_from_games_leaves_without_a_selection():
    async def body():
        app = HomepageApp(games=ALL_GAMES, player_name="Ada")
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.pause()
            await pilot.click("#quit")
            await pilot.pause()
        assert app.return_value is None
        assert app.player_name == "Ada"

    _run(body())


def test_typed_name_submits_with_enter():
    async def body():
        app = HomepageApp(games=["poker"])
        async with app.run_test(size=(80, 24)) as pilot:
            await pilot.click("#name-input")
            await pilot.press(*"sam", "enter")
            await pilot.pause()
            assert isinstance(pilot.app.screen, GameSelectScreen)
            welcome = str(pilot.app.screen.query_one("#welcome", Static).content)
            assert "sam" in welcome

    _run(body())


def test_run_casino_opens_original_game_and_keeps_balance():
    prompts = [
        ("Ada", "slots"),
        ("Ada", "poker"),
        ("Grace", "uno"),
        ("Grace", None),
    ]

    def prompt(games, player_name):
        assert games == ALL_GAMES
        return prompts.pop(0)

    balances = []

    def slots(ctx):
        assert ctx.account.name == "Ada"
        assert ctx.account.balance == ACCOUNT_STARTING_BALANCE
        ctx.account.balance = 40
        balances.append(ctx.account.balance)

    def poker(ctx):
        assert ctx.account.name == "Ada"
        assert ctx.account.balance == 40
        balances.append(ctx.account.balance)

    def uno(ctx):
        assert ctx.account.name == "Grace"
        assert ctx.account.balance == ACCOUNT_STARTING_BALANCE

    handlers = {name: Mock() for name in ALL_GAMES}
    handlers["slots"] = slots
    handlers["poker"] = poker
    handlers["uno"] = uno

    with patch("casino.main.GAME_HANDLERS", handlers), \
         patch("casino.main.clear_screen"), \
         patch("casino.main.display_topbar"), \
         patch("casino.main.cprint"), \
         patch("casino.main.get_theme") as theme:
        run_casino(prompt=prompt)

    theme.assert_not_called()
    handlers["blackjack (U.S.)"].assert_not_called()
    assert balances == [40, 40]
    assert prompts == []


def test_unknown_game_does_not_exit_the_lobby():
    prompts = [("Ada", "not-a-game"), ("Ada", None)]

    def prompt(games, player_name):
        return prompts.pop(0)

    with patch("casino.main.GAME_HANDLERS", {name: Mock() for name in GAME_HANDLERS}), \
         patch("casino.main.clear_screen"), \
         patch("casino.main.display_topbar"), \
         patch("casino.main.cprint") as printed, \
         patch("casino.main.get_theme") as theme:
        run_casino(prompt=prompt)

    theme.assert_not_called()
    printed.assert_any_call("\nNo such game!\n")
    printed.assert_any_call("\nGoodbye!\n")


def test_quit_without_playing_says_goodbye():
    with patch("casino.main.clear_screen"), \
         patch("casino.main.display_topbar") as topbar, \
         patch("casino.main.cprint") as printed, \
         patch("casino.main.get_theme") as theme:
        run_casino(prompt=lambda games, name: ("", None))

    theme.assert_not_called()
    topbar.assert_called_once()
    assert topbar.call_args.args[0] is None
    printed.assert_called_with("\nGoodbye!\n")
