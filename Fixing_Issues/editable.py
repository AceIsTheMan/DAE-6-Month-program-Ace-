import pandas as pd
import taipy.gui.builder as tgb
from taipy.gui import Gui

df = pd.DataFrame({"A": ["a1", "a2", "a3"], "B": ["b1", "b2", "b3"]})
df.set_index("A", inplace=True)
# Fix: with an index set, the table sends the row's position (0, 1, 2),
# not its label (a1, a2, a3). iloc edits by position, so the right row changes.
def edit_cell(state, var_name, payload):
    new_df = state.df.copy()
    col = new_df.columns.get_loc(payload["col"])
    new_df.iloc[payload["index"], col] = payload["value"]
    state.df = new_df

with tgb.Page() as page:
    tgb.table("{df}", editable=True, on_edit=edit_cell)

if __name__ == "__main__":
    gui = Gui(page=page)
    gui.run(title="Default editable behaviour broken when dataframe has index")