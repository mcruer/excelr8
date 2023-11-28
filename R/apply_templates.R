#' Apply Cell Formatting and Data Template to Excel Sheet
#'
#' This internal function applies a range of styles, validation rules, formulas,
#' and data to specific cells in an Excel workbook using the openxlsx package.
#'
#' @param wb A workbook object from openxlsx.
#' @param df A data frame containing the data to be written.
#' @param cell.template A data frame containing cell template information.
#' @param column.names Logical. Should column names be included?
#' @param column.name Name of the column in the data frame.
#' @param sheet.number Numeric or character identifier for the sheet.
#' @param column.number The column number to apply the template to.
#' @param column.type Type of the column ("data", etc.)
#' @param data.length Number of rows to apply the data to.
#' @param data.start.row The starting row for the data.
#' @param validation.type Type of validation ("date", "numeric", etc.)
#' @param validation.operator Operator for validation ("greaterThan", etc.)
#' @param validation.value.1 First value for validation.
#' @param validation.value.2 Second value for validation.
#' @param formula.text Text representation of the Excel formula.
#' @param fontName Font name for cell style.
#' @param fontSize Font size for cell style.
#' @param fontColour Font color for cell style.
#' @param numFmt Number format for cell style.
#' @param border Type of cell border.
#' @param borderColour Color of cell border.
#' @param borderStyle Style of cell border.
#' @param bgFill Background fill for cell style.
#' @param fgFill Foreground fill for cell style.
#' @param halign Horizontal alignment for cell style.
#' @param valign Vertical alignment for cell style.
#' @param textDecoration Text decoration for cell style.
#' @param wrapText Text wrap setting for cell style.
#' @param textRotation Text rotation angle for cell style.
#' @param indent Indentation for cell style.
#' @param locked Logical. Is the cell locked?
#' @param hidden Logical. Is the cell hidden?
#'
#' @return NULL. The function modifies the workbook object in place.
#' @keywords internal
apply_cell_template <- function (wb, #Not from template
                                 df, #Not from template
                                 cell.template, #Not from template (well, it is the template, actually)
                                 column.names = FALSE, #Not from template
                                 column.name,
                                 sheet.number,
                                 column.number,
                                 column.type,
                                 data.length,
                                 data.start.row,
                                 validation.type,
                                 validation.operator,
                                 validation.value.1,
                                 validation.value.2,
                                 formula.text,
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
                                 hidden) {


  #Set Defaults -----------
  if (is.na(data.length))
    data.length <- nrow(df)

  rows <- data.start.row:(data.start.row + data.length - 1)
  validation.value <-
    c(validation.value.1, validation.value.2) %>% stats::na.omit()

  if (is.na(numFmt))
    numFmt <- openxlsx::openxlsx_getOp("numFmt", "GENERAL")
  if (is.na(borderColour))
    borderColour <- openxlsx::openxlsx_getOp("borderColour", "black")
  if (is.na(borderStyle))
    borderStyle <- openxlsx::openxlsx_getOp("borderStyle", "thin")
  if (is.na(wrapText))
    wrapText <- FALSE
  make_null <- function(variable) {
    if (is.na(variable))
      return(NULL)
    return(variable)
  }

  # Use mget to get the variables in a list
  temp.list <- mget(
    c(
      "fontName",
      "fontSize",
      "fontColour",
      "border",
      "bgFill",
      "fgFill",
      "halign",
      "valign",
      "textDecoration",
      "textRotation",
      "indent",
      "locked",
      "hidden"
    )
  )

  # Modify the list
  temp.list <- purrr::map(temp.list, make_null)

  # Assign modified values back to the original variables
  list2env(temp.list, envir = environment())

  #Apply sheet contents to the cells -----

  apply_styles(
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
  )


  if (!is.na(column.type) && column.type == "data") {
    write_data(
      wb = wb,
      df = df,
      column.names = column.names,
      column.name = column.name,
      sheet.number = sheet.number,
      column.number = column.number,
      data.start.row = data.start.row,
      data.length = data.length
    )
  }

  if (!is.na(validation.type)) {

    apply_validation (wb, validation.type, sheet.number, column.number,
                      rows, validation.operator, validation.value)
  }


  if (!is.na(formula.text)) {
    apply_formula(wb, rows, sheet.number, cell.template, column.number,
                  data.start.row, formula.text)
  }

}

#' Apply Template and Protection Settings to Excel Sheet
#'
#' This function applies worksheet protection and visibility settings to an
#' Excel sheet using the openxlsx package.
#'
#' @param wb Workbook object from openxlsx.
#' @param sheet.number Numeric or character identifier for the sheet.
#' @param firstActiveRow The first active row of the worksheet.
#' @param firstActiveCol The first active column of the worksheet.
#' @param protect Logical, whether to protect the worksheet.
#' @param password Character, the password for protecting the worksheet.
#' @param hide Logical, whether to hide the worksheet.
#' @param lock.selecting.locked.cells Logical, whether to allow selection of locked cells.
#' @param lock.selecting.unlocked.cells Logical, whether to allow selection of unlocked cells.
#' @param lock.formatting.cells Logical, whether to allow cell formatting.
#' @param lock.formatting.columns Logical, whether to allow column formatting.
#' @param lock.formatting.rows Logical, whether to allow row formatting.
#' @param lock.inserting.columns Logical, whether to allow inserting columns.
#' @param lock.inserting.rows Logical, whether to allow inserting rows.
#' @param lock.inserting.hyperlinks Logical, whether to allow inserting hyperlinks.
#' @param lock.deleting.columns Logical, whether to allow deleting columns.
#' @param lock.deleting.rows Logical, whether to allow deleting rows.
#' @param lock.sorting Logical, whether to allow sorting.
#' @param lock.auto.filter Logical, whether to allow auto-filtering.
#' @param lock.pivot.tables Logical, whether to allow pivot table operations.
#' @param lock.objects Logical, whether to allow operations on objects.
#' @param lock.scenarios Logical, whether to allow scenario operations.
#'
#' @return NULL. The function modifies the workbook object in place.
#' @keywords internal
apply_sheet_template <- function (wb, #Not from template
                                  sheet.number,
                                  firstActiveRow,
                                  firstActiveCol,
                                  protect,
                                  password,
                                  hide,
                                  lock.selecting.locked.cells,
                                  lock.selecting.unlocked.cells,
                                  lock.formatting.cells,
                                  lock.formatting.columns,
                                  lock.formatting.rows,
                                  lock.inserting.columns,
                                  lock.inserting.rows,
                                  lock.inserting.hyperlinks,
                                  lock.deleting.columns,
                                  lock.deleting.rows,
                                  lock.sorting,
                                  lock.auto.filter,
                                  lock.pivot.tables,
                                  lock.objects,
                                  lock.scenarios) {
  # print (str_c(sheet.number, "row", firstActiveRow, "col", firstActiveCol, sep = "; "))
  #
  # freezePane(wb = wb,
  #            sheet = sheet.number,
  #            firstActiveRow = firstActiveRow,
  #            firstActiveCol = firstActiveCol,
  #            firstRow = FALSE,
  #            firstCol = FALSE
  # )


  openxlsx::protectWorksheet(
    wb,
    sheet = sheet.number,
    protect = protect,
    password = password,
    lock.selecting.locked.cells,
    lock.selecting.unlocked.cells,
    lock.formatting.cells,
    lock.formatting.columns,
    lock.formatting.rows,
    lock.inserting.columns,
    lock.inserting.rows,
    lock.inserting.hyperlinks,
    lock.deleting.columns,
    lock.deleting.rows,
    lock.sorting,
    lock.auto.filter,
    lock.pivot.tables,
    lock.objects,
    lock.scenarios
  )

  openxlsx::sheetVisibility(wb)[sheet.number] <- !hide


}

#' Apply Template and Protection Settings to Excel Workbook
#'
#' This function applies workbook protection and sets the active sheet in
#' an Excel workbook using the openxlsx package.
#'
#' @param wb Workbook object from openxlsx.
#' @param protect Logical, whether to protect the workbook.
#' @param password Character, the password for protecting the workbook.
#' @param lock.structure Logical, whether to lock the structure of the workbook.
#' @param lock.windows Logical, whether to lock the windows of the workbook.
#' @param type Character, workbook type (e.g., 'xlsx', 'xls'). Optional.
#' @param active.sheet Numeric or character identifier for setting the active sheet.
#'
#' @return NULL. The function modifies the workbook object in place.
#' @keywords internal
apply_workbook_template <- function (wb,
                                     protect,
                                     password,
                                     lock.structure,
                                     lock.windows,
                                     type,
                                     active.sheet) {
  openxlsx::activeSheet(wb) <- active.sheet

  openxlsx::protectWorkbook(
    wb,
    protect = protect,
    password = password,
    lockStructure = lock.structure,
    lockWindows = lock.windows,
    type = type
  )

}
