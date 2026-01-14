# Install packages if needed (run once)
# install.packages("quantmod")

library(quantmod)

# Fetch daily data for VIXY and DUST (last 30 days)
symbols <- c("VIXY", "DUST")

for (sym in symbols) {
  cat("\n", paste(rep("=", 60), collapse = ""), "\n")
  cat(sym, "- Daily Pricing Data\n")
  cat(paste(rep("=", 60), collapse = ""), "\n\n")

  # Download data from Yahoo Finance
  getSymbols(sym, src = "yahoo", from = Sys.Date() - 30, to = Sys.Date())

  # Get the data and convert to data frame
  data <- get(sym)
  df <- data.frame(
    Date = index(data),
    Open = as.numeric(Op(data)),
    High = as.numeric(Hi(data)),
    Low = as.numeric(Lo(data)),
    Close = as.numeric(Cl(data)),
    Volume = as.numeric(Vo(data))
  )

  print(df, row.names = FALSE)
}

# Optional: Save to CSV files
# write.csv(VIXY, "vixy_prices.csv")
# write.csv(DUST, "dust_prices.csv")
