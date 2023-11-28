#' Apply Styles to Cells in an Excel Sheet
#'
#' This internal function applies styles to a specific range of cells
#' in an Excel workbook using the openxlsx package.
#'
#' @param wb A workbook object from openxlsx.
#' @param sheet.number Numeric or character identifier for the sheet.
#' @param rows The row range to apply the style to.
#' @param column.number The column number to apply the style to.
#' @param fontName Font name.
#' @param fontSize Font size.
#' @param fontColour Font color.
#' @param numFmt Number format.
#' @param border Border style.
#' @param borderColour Border color.
#' @param borderStyle Border style.
#' @param bgFill Background fill color.
#' @param fgFill Foreground fill color.
#' @param halign Horizontal alignment.
#' @param valign Vertical alignment.
#' @param textDecoration Text decoration.
#' @param wrapText Wrap text.
#' @param textRotation Text rotation angle.
#' @param indent Indentation level.
#' @param locked Lock cells.
#' @param hidden Hide cells.
#'
#' @return NULL. The function modifies the workbook object in place.
#' @keywords internal
apply_styles <- function (
  wb,
  sheet.number,
  rows,
  column.number,
  fontName,
  fontSize,
  fontColour,
  numFmt,
  border,
  borderColour,
  borderStyle,
  bgFill,
  fgFill,
  halign,
  valign,
  textDecoration,
  wrapText,
  textRotation,
  indent,
  locked,
  hidden
) {
  cell.style <- openxlsx::createStyle(
    fontName,
    fontSize,
    fontColour,
    numFmt,
    border,
    borderColour,
    borderStyle,
    bgFill,
    fgFill,
    halign,
    valign,
    textDecoration,
    wrapText,
    textRotation,
    indent,
    locked,
    hidden
  )

  openxlsx::addStyle(
    wb = wb,
    sheet = sheet.number,
    style = cell.style,
    rows = rows,
    cols = column.number,
    stack = TRUE
  )
}

#' Write Data to an Excel Sheet
#'
#' This internal function writes a data frame to a specific sheet and
#' position within an Excel workbook using the openxlsx package.
#'
#' @param wb A workbook object from openxlsx.
#' @param df Data frame to write.
#' @param column.names Boolean, should column names be written.
#' @param column.name Name of the column to select from the data frame.
#' @param sheet.number Numeric or character identifier for the sheet.
#' @param column.number Starting column number for the data.
#' @param data.start.row Starting row number for the data.
#' @param data.length Number of rows to write.
#'
#' @return A modified workbook object from openxlsx.
#' @keywords internal
write_data <- function (wb,
                        df,
                        column.names,
                        column.name,
                        sheet.number,
                        column.number,
                        data.start.row,
                        data.length) {
  data <- df %>%
    dplyr::select(tidyselect::all_of(column.name)) %>%
    utils::head (min(data.length, nrow(df)))

  openxlsx::writeData(
    wb,
    sheet = sheet.number,
    x = data,
    startCol = column.number,
    startRow = data.start.row,
    colNames = column.names
  )

  return(wb)

}

#' Apply Data Validation to Cells in an Excel Sheet
#'
#' This internal function applies data validation to a specific range of cells
#' in an Excel workbook using the openxlsx package. This includes validation
#' for dates and other data types.
#'
#' @param wb A workbook object from openxlsx.
#' @param validation.type The type of data validation to apply.
#' @param sheet.number Numeric or character identifier for the sheet.
#' @param column.number The column number to apply the validation to.
#' @param rows The row range to apply the validation to.
#' @param validation.operator The operator used for validation (e.g., "between", "lessThan").
#' @param validation.value The value or range of values used for validation.
#'
#' @return NULL. The function modifies the workbook object in place.
#' @keywords internal
apply_validation <- function (
  wb,
  validation.type,
  sheet.number,
  column.number,
  rows,
  validation.operator,
  validation.value
) {
  if (validation.type == "date") {
    openxlsx::dataValidation(
      wb,
      sheet = sheet.number,
      col = column.number,
      rows = rows,
      type = "date",
      operator = validation.operator,
      value = as.Date(validation.value)
    )
  }

  else{
    openxlsx::dataValidation(
      wb,
      sheet = sheet.number,
      col = column.number,
      rows = rows,
      operator = validation.operator,
      type = validation.type,
      value = validation.value
    )
  }
}

#' Apply Excel Formulas to Cells in an Excel Sheet
#'
#' This internal function writes Excel formulas to a specific range of cells
#' in an Excel workbook using the openxlsx package.
#'
#' @param wb A workbook object from openxlsx.
#' @param rows The row range to apply the formula to.
#' @param sheet.number Numeric or character identifier for the sheet.
#' @param cell.template A data frame containing cell template information.
#' @param column.number The column number to apply the formula to.
#' @param data.start.row The starting row for the formula.
#' @param formula.text Text representation of the Excel formula.
#'
#' @return NULL. The function modifies the workbook object in place.
#' @keywords internal
apply_formula <- function (
  wb,
  rows,
  sheet.number,
  cell.template,
  column.number,
  data.start.row,
  formula.text){

  x <- generate_xls_formula(formula.text, rows, sheet.number, cell.template)

  openxlsx::writeFormula(
    wb,
    sheet = sheet.number,
    x = x,
    startCol = column.number,
    startRow = data.start.row
  )
}
