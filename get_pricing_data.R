# install.packages(c("quantmod", "purrr"))

library(quantmod)
library(purrr)

fetch_symbol <- function(sym, from_date, to_date) {
  cat(sym, "- Fetching...\n")

  # getSymbols returns the actual object name (^VIX becomes VIX)
  obj_name <- getSymbols(sym, src = "yahoo", from = from_date, to = to_date, auto.assign = TRUE)
  data <- get(obj_name)

  data.frame(
    Symbol = sym,
    Date = index(data),
    Open = as.numeric(Op(data)),
    High = as.numeric(Hi(data)),
    Low = as.numeric(Lo(data)),
    Close = as.numeric(Cl(data)),
    Volume = as.numeric(Vo(data))
  )
}

get_pricing_data <- function(symbols = c("VIXY", "DUST"),
                              days_back = 30,
                              output_file = "pricing_data.csv") {

  from_date <- Sys.Date() - days_back
  to_date <- Sys.Date()

  all_data <- symbols |>
    map(\(sym) fetch_symbol(sym, from_date, to_date)) |>
    list_rbind()

  write.csv(all_data, output_file, row.names = FALSE)
  cat("\nSaved", nrow(all_data), "rows to", output_file, "\n")

  invisible(all_data)
}

# Run with defaults (or customize)
get_pricing_data(
  symbols = c("VIXY", "DUST", "^VIX"),
  days_back = 6000,
  output_file = "full_period_prices.csv"
)
