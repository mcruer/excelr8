# Install packages if needed (run once)
# install.packages("quantmod")

library(quantmod)

# Fetch daily data for VIXY and DUST (last 30 days)
symbols <- c("VIXY", "DUST")
all_data <- data.frame()

for (sym in symbols) {
  cat("\n", paste(rep("=", 60), collapse = ""), "\n")
  cat(sym, "- Daily Pricing Data\n")
  cat(paste(rep("=", 60), collapse = ""), "\n\n")

  # Download data from Yahoo Finance
  getSymbols(sym, src = "yahoo", from = Sys.Date() - 30, to = Sys.Date())

  # Get the data and convert to data frame
  data <- get(sym)
  df <- data.frame(
    Symbol = sym,
    Date = index(data),
    Open = as.numeric(Op(data)),
    High = as.numeric(Hi(data)),
    Low = as.numeric(Lo(data)),
    Close = as.numeric(Cl(data)),
    Volume = as.numeric(Vo(data))
  )

  print(df, row.names = FALSE)
  all_data <- rbind(all_data, df)
}

# Save combined data to CSV
output_file <- "pricing_data.csv"
write.csv(all_data, output_file, row.names = FALSE)
cat("\n", paste(rep("=", 60), collapse = ""), "\n")
cat("Data saved to:", output_file, "\n")
cat("Total rows:", nrow(all_data), "\n")
