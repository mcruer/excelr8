utils::globalVariables(c("column.name", "column.number"))

#' Generate Excel Formulas
#'
#' This internal function generates Excel formulas based on a given text template
#' and additional parameters.
#'
#' @param text Text representation of the Excel formula.
#' @param rows Row range to use in the formula.
#' @param sheet.number Numeric or character identifier for the sheet.
#' @param cell.template A data frame containing cell template information.
#'
#' @return A string representing the Excel formula.
#' @keywords internal
generate_xls_formula <- function (text, rows, sheet.number, cell.template) {

  sheet.number.filter <- sheet.number

  cell.template <- cell.template %>%
    dplyr::filter (sheet.number == sheet.number.filter)

  column.name <- cell.template %>%
    dplyr::pull (column.name)

  temp <- function (string, target) {
    string %>%
      stringr::str_replace(target, stringr::str_c("{xls('", target, "', rows, sheet.number, cell.template)}"))
  }

  text %>%
    listful::build(column.name, temp) %>%
    glue::glue()

}

#' Generate Excel Cell References
#'
#' This internal function generates Excel cell references based on variable names,
#' rows, and a cell template.
#'
#' @param var.name Name of the variable.
#' @param rows Row range to use in the reference.
#' @param sheet.number Numeric or character identifier for the sheet.
#' @param cell.template A data frame containing cell template information.
#'
#' @return A string representing the Excel cell reference.
#' @keywords internal
xls <- function (var.name, rows, sheet.number, cell.template) {

  sheet.number.filter <- sheet.number


  col.letter <- cell.template %>%
    dplyr::filter(column.name == var.name,
           sheet.number == sheet.number.filter) %>%
    dplyr::pull(column.number) %>%
    xls_col()

  paste0(col.letter, rows)
}

#' Convert Column Number to Excel Column Letter
#'
#' This internal function converts a numeric column index to its Excel
#' column letter equivalent.
#'
#' @param col_number Numeric index of the column.
#'
#' @return A string representing the Excel column letter.
#' @keywords internal
xls_col <- function(col_number) {
  if (col_number < 1) {
    stop("Column number must be greater than or equal to 1")
  }

  col_name <- ""

  while (col_number > 0) {
    remainder <- (col_number - 1) %% 26
    col_name <- paste0(base::LETTERS[remainder + 1], col_name)
    col_number <- (col_number - remainder - 1) %/% 26
  }

  return(col_name)
}

