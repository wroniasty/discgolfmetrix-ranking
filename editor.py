from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.widgets import Tree, DataTable, Button, ContentSwitcher, Footer, Log, Input, \
    Static, Label
from textual.containers import Vertical, Container
from textual.screen import ModalScreen

import pickle
import pdga

import models
from metrix import MetrixAPI


class PlayerInputModal(ModalScreen[models.Player]):

    BINDINGS = [
        Binding("escape", "dismiss(None)", "Cancel"),
    ]

    DEFAULT_CSS = """
    PlayerInputModal {
        align: center middle;
    }

    PlayerInputModal > Container {
        width: auto;
        height: auto;
        border: thick $background 80%;
    }

    PlayerInputModal > Container > Input {
        width: 60;
    }
    """

    def __init__(self, player, **kwargs):
        self._player = player
        super().__init__(**kwargs)

    def compose(self) -> ComposeResult:
        with Container():
            yield Static(self._player.name)
            yield Label("PDGA ID")
            yield Input(id="data_pdga_id", value=f"{self._player.pdga_id or ''}", type="integer")
            yield Label("PDGA rating")
            yield Input(id="data_pdga_rating", value=f"{self._player.pdga_rating or ''}", type="integer")
            yield Button("Submit", id="submit")
            yield Button("Cancel", id="cancel")
            #yield Button("Fetch from PDGA", id="fetch")

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "submit":
            self._player.pdga_id = int(self.query_one("Input#data_pdga_id").value or 0)
            self._player.pdga_rating = int(self.query_one("Input#data_pdga_rating").value or 0)
            self.dismiss(self._player)
        elif event.button.id == "cancel":
            self.dismiss(None)
        elif event.button.id == "fetch":
            pass
            #self.action_fetch()
        event.stop()

    def on_input_submitted(self, event: Input.Submitted):
        event.stop()


class PlayersWidget(DataTable):
    BINDINGS = [
        Binding("f8", "fetch()", "Fetch from PDGA"),
        Binding("f4", "edit()", "Edit player")
    ]

    # DEFAULT_CSS = """
    #     Screen {
    #     }
    #
    #     #data_input {
    #     }
    #     """


    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.edited_cell = None
        self.edited_player = None

        self.add_column("Metrix ID", key="id")
        self.add_column("Name", key="name")
        self.add_column("PDGA ID", key="pdga_id")
        self.add_column("PDGA Rating", key="pdga_rating")

        self.players = {}

    def add_player(self, player: models.Player):
        self.players[self.add_row(player.id, player.name, player.pdga_id, player.pdga_rating)] = player

    # def compose(self) -> ComposeResult:
    #     yield PlayerDataTable(id="players")

    def on_data_table_cell_highlighted(self, event: DataTable.CellHighlighted):
        table = self
        self.edited_player = table.players[event.cell_key.row_key]
        self.edited_cell = event.cell_key

    def action_edit(self):
        self.app.push_screen(PlayerInputModal(player=self.edited_player),
                             lambda v: self.update_current_row(v) if v is not None else None)

    def update_current_row(self, player=None):
        player = player or self.edited_player
        table = self
        table.update_cell(self.edited_cell.row_key, "pdga_id", player.pdga_id)
        table.update_cell(self.edited_cell.row_key, "pdga_rating", player.pdga_rating)

    def action_fetch(self):
        table = self

        rating = 0
        if not (self.edited_player.pdga_id or 0 > 0):
            pdga_id, rating = pdga.search_player(self.edited_player.name)
            if pdga_id is not None:
                self.edited_player.pdga_id = pdga_id
                self.edited_player.pdga_rating = rating
                self.update_current_row()
                self.app.notify(f"Fetched PDGA ID {pdga_id} rating {rating} for {self.edited_player}")
            else:
                self.edited_player.pdga_id = -1
                self.edited_player.pdga_rating = 0
                self.update_current_row()
                self.app.notify(f"PDGA ID not found for {self.edited_player.name}")

        if self.edited_player.pdga_id > 0 and rating == 0:
            rating, name = pdga.get_player_rating(self.edited_player.pdga_id)
            if rating is not None:
                self.edited_player.pdga_rating = rating
                self.update_current_row()
                self.app.notify(f"Fetched PDGA rating {rating} for {self.edited_player}")
            else:
                self.edited_player.pdga_rating = 0
                self.update_current_row()
                table.update_cell(self.edited_cell.row_key, "pdga_rating", 0)
                self.app.notify(f"PDGA rating not found for {self.edited_player.pdga_id}")


# class PlayerDataTable(DataTable):
#
#     def __init__(self, **kwargs):
#         super().__init__(**kwargs)
#
#         self.add_column("Metrix ID", key="id")
#         self.add_column("Name", key="name")
#         self.add_column("PDGA ID", key="pdga_id")
#         self.add_column("PDGA Rating", key="pdga_rating")
#
#         self.players = {}
#
#     def add_player(self, player: models.Player):
#         self.players[self.add_row(player.id, player.name, player.pdga_id, player.pdga_rating)] = player
#

class CacheEditorApp(App):
    CSS_PATH = "editor.tcss"
    BINDINGS = [
        Binding("f2", "save()", "Save"),
        Binding("f5", "switch_content('players')", "Players"),
        Binding("f6", "switch_content('competitions')", "Competitions"),
        Binding("f7", "switch_content('ratings')", "Ratings"),
        Binding("f9", "switch_content('log')", "Log", show=False),
    ]

    def __init__(self, args):
        super().__init__()
        self.args = args
        self.api = MetrixAPI(cache_file=args.cache_file)

    def on_mount(self) -> None:
        player_table = self.query_one("DataTable#players")
        self._log = self.query_one("Log")

        tree = self.query_one("Tree#competitions")
        for c_id in self.api.cache['competitions']:
            self._log.write_line(f"Competition {c_id}")
            c = self.api.results(c_id)
            c_node = tree.root.add(c.name, data=c, expand=True)
            for c_sub in c.sub:
                r_node = c_node.add(c_sub.name, data=c_sub)
                for i, r in enumerate(sorted(c_sub.results, key=lambda r: r.sum)):
                    r_node.add(f"{i+1:2}. {r.player.name} {'[red]+' if r.diff > 0 else '[green]'}{r.diff}[/] ({r.sum}) rating=[yellow]{r.rating}[/yellow]", data=r)

        for p in set(self.api.players.values()):
            player_table.add_player(p)

        self._log.write_line(f"Players: {len(self.api.cache['players'])}")

    def compose(self) -> ComposeResult:
        # yield PlayersWidget(id="players")
        # yield Tree("Competitions", id="competitions")
        # yield Log(id="log")
        with ContentSwitcher(initial="players"):
            yield PlayersWidget(id="players")
            yield Tree("Competitions", id="competitions")
            yield DataTable(id="ratings")
            yield Log(id="log")

        yield Footer()

    def action_switch_content(self, content_id: str):
        cs = self.query_one("ContentSwitcher")
        cs.current = content_id

    def on_button_pressed(self, event: Button.Pressed):
        self.query_one("ContentSwitcher").current = event.button.id

    def action_save(self):
        self.api.save_cache()
        self.notify(f"Cache saved [{self.api._cache_file}]")


def main(args):
    app = CacheEditorApp(args)
    app.run()


if __name__ == "__main__":
    import argparse
    import os

    argparser = argparse.ArgumentParser()
    argparser.add_argument('--cache-file', '-c', type=str,
                           default=os.path.join(os.path.dirname(os.path.realpath(__file__)),
                                                'results.cache.pkl')
                           )
    main(argparser.parse_args())
