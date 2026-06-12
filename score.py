import polars as pl

current_results = (
    pl.read_csv("current_movie_results.csv")
    .rename(
        {
            "domestic_box_office": "box_office",
            "metacritic_score": "metacritic",
        }
    )
    .select("title", "box_office", "metacritic")
)
predictions = (
    pl.read_csv("summer_movie_preview_predictions.csv")
    .with_columns(pl.col("box_office") * 1_000_000)
    .rename({"box_office": "box_office_pred", "matacritic": "metacritic_pred"})
)  # typo


# Merge the two DataFrames on the 'movie_title' column
merged_df = (
    predictions.join(current_results, on="title", how="left")
    .with_columns(
        (pl.col("box_office_pred") - pl.col("box_office")).alias("box_office_diff"),
        (pl.col("metacritic_pred") - pl.col("metacritic")).alias("metacritic_diff"),
    )
    .with_columns(
        pl.when(pl.col("box_office_diff").abs() <= 1_000_000)
        .then(20)
        .when(pl.col("box_office_diff").abs() <= 5_000_000)
        .then(10)
        .when(pl.col("box_office_diff").abs() <= 10_000_000)
        .then(5)
        .when(pl.col("box_office_diff").abs() <= 50_000_000)
        .then(1)
        .otherwise(0)
        .alias("box_office_pts"),
        pl.when(pl.col("metacritic_diff") == 0)
        .then(5)
        .when(pl.col("metacritic_diff").abs() <= 5)
        .then(1)
        .otherwise(0)
        .alias("metacritic_pts"),
    )
    .with_columns(
        (pl.col("box_office_pts") + pl.col("metacritic_pts")).alias("total_pts")
    )
)

merged_df.write_csv("scores.csv")
