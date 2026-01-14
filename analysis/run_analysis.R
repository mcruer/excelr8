# run_analysis.R - Main analysis script for volatility shorting strategies

# Set working directory to project root
setwd(here::here())

source("analysis/helpers.R")
source("analysis/backtest.R")

# =============================================================================
# Load and prepare data
# =============================================================================

cat("Loading data...\n")
prices <- load_prices("full_period_prices.csv")

# Split by symbol
symbols <- split_by_symbol(prices)
vix_df <- symbols[["^VIX"]]
vixy_df <- symbols[["VIXY"]] |> add_vix(vix_df)
dust_df <- symbols[["DUST"]] |> add_vix(vix_df)

cat(sprintf("Data range: %s to %s\n",
            min(prices$Date), max(prices$Date)))
cat(sprintf("VIX range: %.1f to %.1f (mean: %.1f)\n",
            min(vix_df$Close, na.rm = TRUE),
            max(vix_df$Close, na.rm = TRUE),
            mean(vix_df$Close, na.rm = TRUE)))

# =============================================================================
# Run strategy comparison
# =============================================================================

cat("\n", strrep("=", 70), "\n")
cat("STRATEGY COMPARISON\n")
cat(strrep("=", 70), "\n\n")

comparison <- compare_strategies(vixy_df, dust_df, 5000)

# Calculate annualized returns (approximate years)
years <- as.numeric(diff(range(prices$Date))) / 365
comparison$Annual_Return <- ((1 + comparison$Total_Return)^(1/years) - 1)

# Print results
comparison |>
  mutate(
    PnL = fmt_currency(PnL),
    Max_Exposure = fmt_currency(Max_Exposure),
    Total_Return = fmt_pct(Total_Return * 100),
    Annual_Return = fmt_pct(Annual_Return * 100)
  ) |>
  print()

# =============================================================================
# Quarterly breakdown for baseline strategy
# =============================================================================

cat("\n", strrep("=", 70), "\n")
cat("QUARTERLY P&L (BASELINE STRATEGY)\n")
cat(strrep("=", 70), "\n\n")

quarterly_pnl <- function(df, initial_investment = 5000) {
  quarters <- unique(df$Quarter)

  results <- lapply(quarters, function(q) {
    q_data <- df |> filter(Quarter == q)
    if (nrow(q_data) == 0) return(NULL)

    result <- backtest_baseline(q_data, initial_investment)

    data.frame(
      Quarter = q,
      Entry = q_data$Close[1],
      Exit = q_data$Close[nrow(q_data)],
      PnL = result$pnl,
      Max_Exposure = result$max_exposure
    )
  })

  do.call(rbind, results)
}

vixy_quarterly <- quarterly_pnl(vixy_df) |>
  rename(VIXY_PnL = PnL, VIXY_Max = Max_Exposure) |>
  select(Quarter, VIXY_PnL, VIXY_Max)

dust_quarterly <- quarterly_pnl(dust_df) |>
  rename(DUST_PnL = PnL, DUST_Max = Max_Exposure) |>
  select(Quarter, DUST_PnL, DUST_Max)

quarterly <- vixy_quarterly |>
  left_join(dust_quarterly, by = "Quarter") |>
  mutate(
    Combined_PnL = VIXY_PnL + DUST_PnL,
    Combined_Max = VIXY_Max + DUST_Max
  )

print(quarterly, n = 100)

# =============================================================================
# Annual summary
# =============================================================================

cat("\n", strrep("=", 70), "\n")
cat("ANNUAL SUMMARY\n")
cat(strrep("=", 70), "\n\n")

annual <- quarterly |>
  mutate(Year = substr(as.character(Quarter), 1, 4)) |>
  group_by(Year) |>
  summarize(
    VIXY_PnL = sum(VIXY_PnL, na.rm = TRUE),
    DUST_PnL = sum(DUST_PnL, na.rm = TRUE),
    Combined_PnL = sum(Combined_PnL, na.rm = TRUE),
    Peak_Exposure = max(Combined_Max, na.rm = TRUE),
    .groups = "drop"
  )

print(annual, n = 100)

# =============================================================================
# VIX Fade trade details
# =============================================================================

cat("\n", strrep("=", 70), "\n")
cat("VIX FADE TRADES (Entry >30, Exit <20)\n")
cat(strrep("=", 70), "\n\n")

fade_result <- backtest_vix_fade(vixy_df, 5000, 30, 20)

if (length(fade_result$trades) > 0) {
  trades_df <- do.call(rbind, lapply(fade_result$trades, as.data.frame))
  print(trades_df)

  cat(sprintf("\nTotal trades: %d\n", nrow(trades_df)))
  cat(sprintf("Winners: %d\n", sum(trades_df$pnl > 0)))
  cat(sprintf("Total P&L: %s\n", fmt_currency(sum(trades_df$pnl))))
  cat(sprintf("Avg hold period: %.0f days\n", mean(trades_df$days)))
}

# =============================================================================
# Summary
# =============================================================================

cat("\n", strrep("=", 70), "\n")
cat("GRAND TOTALS\n")
cat(strrep("=", 70), "\n\n")

cat(sprintf("VIXY Total P&L:     %s\n", fmt_currency(sum(quarterly$VIXY_PnL))))
cat(sprintf("DUST Total P&L:     %s\n", fmt_currency(sum(quarterly$DUST_PnL))))
cat(sprintf("Combined Total P&L: %s\n", fmt_currency(sum(quarterly$Combined_PnL))))
cat(sprintf("Peak Exposure:      %s\n", fmt_currency(max(quarterly$Combined_Max))))
cat(sprintf("Data Period:        %.1f years\n", years))
