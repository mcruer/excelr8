# backtest.R - Strategy backtesting functions

source("analysis/helpers.R")

#' Simulate baseline short strategy
#' Short $X, top up when position drops below $X
#' @param df Price data for single symbol
#' @param initial_investment Starting position size
#' @return List with P&L, max_exposure, capital_deployed
backtest_baseline <- function(df, initial_investment = 5000) {
  df <- df |> arrange(Date)

  entry_price <- df$Close[1]
  shares <- initial_investment / entry_price
  total_capital <- initial_investment
  max_exposure <- initial_investment

  for (i in seq_len(nrow(df))) {
    exposure <- shares * df$High[i]
    max_exposure <- max(max_exposure, exposure)

    close_exposure <- shares * df$Close[i]
    if (close_exposure < initial_investment) {
      top_up <- initial_investment - close_exposure
      shares <- shares + top_up / df$Close[i]
      total_capital <- total_capital + top_up
    }
  }

  final_value <- shares * df$Close[nrow(df)]
  pnl <- total_capital - final_value

  list(
    pnl = pnl,
    max_exposure = max_exposure,
    capital_deployed = total_capital,
    total_return = pnl / max_exposure
  )
}

#' Simulate with 2x stop-loss
#' Close position if exposure hits 2x initial, re-enter next quarter
#' @param df Price data for single symbol
#' @param initial_investment Starting position size
#' @param stop_multiple Multiple at which to stop out (default 2)
#' @return List with P&L, max_exposure, capital_deployed
backtest_stop_loss <- function(df, initial_investment = 5000, stop_multiple = 2) {
  df <- df |> arrange(Date)

  total_pnl <- 0
  total_capital <- 0
  max_exposure <- 0

  quarters <- unique(df$Quarter)

  for (q in quarters) {
    q_data <- df |> filter(Quarter == q)
    if (nrow(q_data) == 0) next

    entry_price <- q_data$Close[1]
    shares <- initial_investment / entry_price
    quarter_capital <- initial_investment
    stopped_out <- FALSE
    exit_price <- NULL
    quarter_max <- initial_investment

    for (i in seq_len(nrow(q_data))) {
      if (stopped_out) break

      exposure <- shares * q_data$High[i]
      quarter_max <- max(quarter_max, exposure)

      if (exposure >= initial_investment * stop_multiple) {
        exit_price <- q_data$High[i]
        stopped_out <- TRUE
        break
      }

      close_exposure <- shares * q_data$Close[i]
      if (close_exposure < initial_investment) {
        top_up <- initial_investment - close_exposure
        shares <- shares + top_up / q_data$Close[i]
        quarter_capital <- quarter_capital + top_up
      }
    }

    if (!stopped_out) {
      exit_price <- q_data$Close[nrow(q_data)]
    }

    quarter_pnl <- quarter_capital - (shares * exit_price)
    total_pnl <- total_pnl + quarter_pnl
    total_capital <- total_capital + quarter_capital
    max_exposure <- max(max_exposure, quarter_max)
  }

  list(
    pnl = total_pnl,
    max_exposure = max_exposure,
    capital_deployed = total_capital,
    total_return = total_pnl / max_exposure
  )
}

#' Simulate VIX regime-based sizing
#' VIX < 15: full position, VIX 15-25: half, VIX > 25: exit
#' @param df Price data with VIX column
#' @param initial_investment Base position size
#' @return List with P&L, max_exposure, capital_deployed
backtest_vix_regime <- function(df, initial_investment = 5000) {
  df <- df |> arrange(Date) |> filter(!is.na(VIX))

  total_pnl <- 0
  total_capital <- 0
  max_exposure <- 0

  shares <- 0
  current_capital <- 0

  for (i in seq_len(nrow(df))) {
    vix <- df$VIX[i]
    price <- df$Close[i]

    # Determine target based on VIX
    if (vix < 15) {
      target <- initial_investment
    } else if (vix <= 25) {
      target <- initial_investment / 2
    } else {
      target <- 0
    }

    current_value <- shares * price

    if (target == 0 && shares > 0) {
      # Close position
      pnl <- current_capital - current_value
      total_pnl <- total_pnl + pnl
      total_capital <- total_capital + current_capital
      shares <- 0
      current_capital <- 0
    } else if (target > 0 && shares == 0) {
      # Open new position
      shares <- target / price
      current_capital <- target
    } else if (target > 0 && current_value < target) {
      # Top up
      top_up <- target - current_value
      shares <- shares + top_up / price
      current_capital <- current_capital + top_up
    }

    if (shares > 0) {
      exposure <- shares * df$High[i]
      max_exposure <- max(max_exposure, exposure)
    }
  }

  # Close any remaining position
  if (shares > 0) {
    final_value <- shares * df$Close[nrow(df)]
    pnl <- current_capital - final_value
    total_pnl <- total_pnl + pnl
    total_capital <- total_capital + current_capital
  }

  list(
    pnl = total_pnl,
    max_exposure = max_exposure,
    capital_deployed = total_capital,
    total_return = if (max_exposure > 0) total_pnl / max_exposure else 0
  )
}

#' Simulate VIX fade strategy
#' Only enter after VIX spikes above threshold, exit when VIX drops below exit_level
#' @param df Price data with VIX column
#' @param initial_investment Base position size
#' @param entry_threshold VIX level to enter (default 30)
#' @param exit_threshold VIX level to exit (default 20)
#' @return List with P&L, max_exposure, trades
backtest_vix_fade <- function(df, initial_investment = 5000,
                               entry_threshold = 30, exit_threshold = 20) {
  df <- df |> arrange(Date) |> filter(!is.na(VIX))

  total_pnl <- 0
  total_capital <- 0
  max_exposure <- 0
  trades <- list()

  in_position <- FALSE
  shares <- 0
  entry_capital <- 0
  entry_date <- NULL
  entry_vix <- NULL

  for (i in seq_len(nrow(df))) {
    vix <- df$VIX[i]
    price <- df$Close[i]

    if (!in_position && vix >= entry_threshold) {
      # Enter position
      shares <- initial_investment / price
      entry_capital <- initial_investment
      entry_date <- df$Date[i]
      entry_vix <- vix
      in_position <- TRUE
    } else if (in_position) {
      # Track exposure
      exposure <- shares * df$High[i]
      max_exposure <- max(max_exposure, exposure)

      # Top up if needed
      close_exp <- shares * price
      if (close_exp < initial_investment) {
        top_up <- initial_investment - close_exp
        shares <- shares + top_up / price
        entry_capital <- entry_capital + top_up
      }

      # Exit when VIX drops
      if (vix < exit_threshold) {
        exit_value <- shares * price
        pnl <- entry_capital - exit_value

        trades <- c(trades, list(list(
          entry_date = entry_date,
          exit_date = df$Date[i],
          days = as.numeric(df$Date[i] - entry_date),
          entry_vix = entry_vix,
          exit_vix = vix,
          capital = entry_capital,
          pnl = pnl
        )))

        total_pnl <- total_pnl + pnl
        total_capital <- total_capital + entry_capital
        in_position <- FALSE
        shares <- 0
        entry_capital <- 0
      }
    }
  }

  # Close any remaining position
  if (in_position) {
    exit_value <- shares * df$Close[nrow(df)]
    pnl <- entry_capital - exit_value
    total_pnl <- total_pnl + pnl
    total_capital <- total_capital + entry_capital
  }

  list(
    pnl = total_pnl,
    max_exposure = max_exposure,
    capital_deployed = total_capital,
    total_return = if (max_exposure > 0) total_pnl / max_exposure else 0,
    trades = trades
  )
}

#' Run all strategies and compare
#' @param vixy_df VIXY data with VIX column
#' @param dust_df DUST data with VIX column
#' @param initial_investment Base position size
#' @return Data frame comparing all strategies
compare_strategies <- function(vixy_df, dust_df, initial_investment = 5000) {
  results <- list()

  # Baseline
  vixy_base <- backtest_baseline(vixy_df, initial_investment)
  dust_base <- backtest_baseline(dust_df, initial_investment)
  results$baseline <- list(
    name = "Baseline (always in)",
    pnl = vixy_base$pnl + dust_base$pnl,
    max_exposure = vixy_base$max_exposure + dust_base$max_exposure
  )

  # 2x Stop
  vixy_stop <- backtest_stop_loss(vixy_df, initial_investment, 2)
  dust_stop <- backtest_stop_loss(dust_df, initial_investment, 2)
  results$stop_2x <- list(
    name = "2x Stop Loss",
    pnl = vixy_stop$pnl + dust_stop$pnl,
    max_exposure = vixy_stop$max_exposure + dust_stop$max_exposure
  )

  # DUST only
  results$dust_only <- list(
    name = "DUST Only",
    pnl = dust_base$pnl,
    max_exposure = dust_base$max_exposure
  )

  # VIX Regime
  vixy_regime <- backtest_vix_regime(vixy_df, initial_investment)
  dust_regime <- backtest_vix_regime(dust_df, initial_investment)
  results$vix_regime <- list(
    name = "VIX Regime Sizing",
    pnl = vixy_regime$pnl + dust_regime$pnl,
    max_exposure = vixy_regime$max_exposure + dust_regime$max_exposure
  )

  # VIX Fade (VIXY only)
  vixy_fade <- backtest_vix_fade(vixy_df, initial_investment, 30, 20)
  results$vix_fade <- list(
    name = "VIX Fade >30 (VIXY)",
    pnl = vixy_fade$pnl,
    max_exposure = vixy_fade$max_exposure
  )

  # Convert to data frame
  do.call(rbind, lapply(results, function(r) {
    data.frame(
      Strategy = r$name,
      PnL = r$pnl,
      Max_Exposure = r$max_exposure,
      Total_Return = r$pnl / r$max_exposure,
      stringsAsFactors = FALSE
    )
  }))
}
