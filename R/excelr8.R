utils::globalVariables(c("default", "sheet.number"))

#' Write Excel File from Datasheet Template
#'
#' This function generates an Excel file based on data and optional formatting templates.
#' It allows you to apply cell, sheet, and workbook templates to an existing or new workbook.
#'
#' @param df Data frame containing the data to be written to the Excel file.
#' @param data.template.path Character string specifying the path to the Excel file serving as the data template.
#' @param formatting.template.path Character string specifying the path to the Excel file serving as the formatting template. Default is NULL.
#' @param wb Workbook object from openxlsx. Default is NULL.
#' @param output.file.name Character string specifying the name of the output Excel file. Default is NULL.
#' @param unique_identifier This is necessary for use of the comments function.
#' Provide a unique identifier associated with the data to apply automatic comments to.
#' Default is NULL. If Null, the comments functionality is disabled.
#' @param column.names Logical indicating whether to include column names. Default is FALSE.
#' @param messages_first_data_row An intiger indicating which rows the messages start at. Default is NULL.
#' If NULL, the program looks to the Cell Info tab of the workbook template to infer a logical value.
#' @importFrom magrittr %>%
#' @return If output.file.name is NULL, returns the modified workbook object. Otherwise, it saves the workbook and returns NULL.
#' @export
#' @examples
#' \dontrun{
#' excelr8(df = data.frame(a = 1:3, b = 4:6),
#'                               data.template.path = "path/to/data_template.xlsx",
#'                               output.file.name = "output.xlsx")
#' }
#'
excelr8 <- function(df,
                    data.template.path,
                    formatting.template.path = NULL,
                    wb=NULL,
                    output.file.name = NULL,
                    unique_identifier = NULL,
                    column.names = FALSE,
                    messages_first_data_row = NULL
) {

  #Figure out if the wb was provided or needs to be created.
  formatting.template.included <- !is.null(formatting.template.path)
  if(formatting.template.included) {
    wb <- openxlsx::loadWorkbook(formatting.template.path)
  } else if (is.null(wb)) {
    wb <- openxlsx::createWorkbook()
  }


  #Apply the default to the formatting template -----
  apply.default <- function (df) {
    df %>%
      gplyr::pipe_assign("default", ~.x %>% dplyr::slice(1) %>% as.list) %>%
      purrr::modify2(default, ~tidyr::replace_na(.x, .y)) %>%
      dplyr::slice(-1)
  }

  cell.template <- readxl::read_excel(data.template.path) %>%
    apply.default ()
  sheet.template <- readxl::read_excel(data.template.path, sheet = 2)  %>%
    apply.default()

  workbook.template <- readxl::read_excel(data.template.path, sheet = 3) %>%
    apply.default()

  # if (!formatting.template.included) {
  #   sheet.count <- max (
  #     cell.template %>% dplyr::pull(sheet.number) %>% max(),
  #     sheet.template %>% dplyr::pull(sheet.number) %>% max()
  #   )
  #   purrr::walk (1:sheet.count, ~addWorksheet(wb, stringr::str_c("Sheet", .x)))
  # }


  #Uses Cell Template -------------

  purrr::pwalk(cell.template, apply_cell_template,
        wb = wb,
        df = df,
        cell.template = cell.template)

  #Requires Sheet Template -----
  purrr::pwalk (sheet.template, apply_sheet_template, wb = wb)


  #Requires workbook template -------------
  purrr::pwalk(workbook.template, apply_workbook_template, wb = wb)

  unique_identifier_quo <- rlang::enquo(unique_identifier) # Capture the unique identifier as a quosure
  if(!rlang::quo_is_null(unique_identifier_quo)) {
    comments <- generate_messages_df(df,
                                     data.template.path,
                                     unique_identifier = {{unique_identifier}},
                                     first_data_row = messages_first_data_row)

    wb <- wb %>%
      listful::pbuild (comments, write_comment)
  }

  conditional_formatting <- readxl::read_excel(data.template.path, sheet = "Conditional Formatting", skip = 1)

  wb <- wb %>%
    listful::pbuild(conditional_formatting, add_conditional_formatting)

  #Final Steps -----


  if(is.null(output.file.name)) {return (wb)}

  openxlsx::saveWorkbook(wb, output.file.name, overwrite = TRUE)
}
