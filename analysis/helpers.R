# helpers.R - Utility functions for volatility analysis

library(dplyr)
library(tidyr)
library(lubridate)

#' Load and prepare pricing data
#' @param file_path Path to CSV file
#' @return Cleaned data frame with Date as Date type
load_prices <- function(file_path = "full_period_prices.csv") {
  read.csv(file_path, stringsAsFactors = FALSE) |>
    mutate(
      Date = as.Date(Date),
      Quarter = quarter(Date, with_year = TRUE)
    ) |>
    arrange(Symbol, Date)
}

#' Split pricing data by symbol
#' @param df Data frame from load_prices
#' @return Named list of data frames
split_by_symbol <- function(df) {
  df |>
    group_by(Symbol) |>
    group_split() |>
    setNames(unique(df$Symbol))
}

#' Join VIX to another symbol's data
#' @param df Data frame for one symbol
#' @param vix_df VIX data frame
#' @return Data frame with VIX column added
add_vix <- function(df, vix_df) {
  vix_lookup <- vix_df |>
    select(Date, VIX = Close)

  df |>
    left_join(vix_lookup, by = "Date")
}

#' Calculate returns
#' @param prices Vector of prices
#' @return Vector of simple returns
calc_returns <- function(prices) {
  c(NA, diff(prices) / head(prices, -1))
}

#' Summarize by quarter
#' @param df Data frame with Quarter column
#' @param ... Columns to summarize
summarize_quarterly <- function(df, ...) {
  df |>
    group_by(Quarter) |>
    summarize(..., .groups = "drop")
}

#' Format currency for display
fmt_currency <- function(x, digits = 0) {
  sprintf("$%s", format(round(x, digits), big.mark = ",", scientific = FALSE))
}

#' Format percentage for display
fmt_pct <- function(x, digits = 1) {
  sprintf("%.*f%%", digits, x)
}
