generate_messages_df <- function (df,
                                  workbook_template_path,
                                  first_data_row = NULL) {

  codify <- function(df, text) {
    eval(parse(text = paste0("df %>% ", text)))
  }

  cell_template <- readxl::read_excel(workbook_template_path, "Cell Info") #

  messages_template <-
    readxl::read_excel(workbook_template_path, sheet = "Messages")

  if (nrow (gplyr::filter_in_na(messages_template,
                                target, message, execute,
                                if_any_or_all = "if_any")) > 0){
    stop("The message tab of the worksheet template is missing values.")
  }

  messages_template <- messages_template %>%
    dplyr::left_join(cell_template %>%
                       dplyr::select(column.name, sheet.number) %>%
                       rlang::set_names(c("target", "sheet")))

  if (nrow (gplyr::filter_in_na(messages_template,
                                sheet,
                                if_any_or_all = "if_any")) > 0){
    stop("Target columns on the Messages sheet of the worksheet template do not match
         the columns in the Cell Info sheet.")
  }

  error_messages <- messages_template %>%
    dplyr::select (name, sheet, message, author)

  expressions <- messages_template %>%
    gplyr::filter_out_na(execute) %>%
    dplyr::pull (execute)

  if (is.null(first_data_row)) {
    data_start_row <-
      cell_template %>%
      dplyr::pull(data.start.row) %>%
      stats::median(na.rm = TRUE)
  }

  column_location <-
    cell_template %>%
    dplyr::select (column.name, column.number) %>%
    rlang::set_names(c("column_name", "column_number"))

  row_location <- df %>%
    gplyr::add_index(col_name = row_number) %>%
    gplyr::quickm(row_number, magrittr::add, data_start_row - 1) %>%
    dplyr::select(project_id, row_number)

  messages <- df %>%
    listful::build(expressions, codify) %>%
    dplyr::select(project_id, dplyr::starts_with("error_")) %>%
    purrr::modify_if(is.logical, gplyr::na_to_F) %>%
    tidyr::pivot_longer(cols = -project_id) %>%
    dplyr::filter (value) %>%
    dplyr::left_join(error_messages) %>%
    gplyr::quickm(name, stringr::str_remove, "error_") %>%
    tidyr::separate(name,
                    into = c("column_name", "index"),
                    sep = "_N") %>%
    dplyr::select(-index, -value) %>%
    dplyr::group_by(project_id, sheet, column_name, author) %>%
    gplyr::quicks(message, stringr::str_c, collapse = "; ") %>%
    dplyr::left_join(column_location) %>%
    dplyr::left_join(row_location) %>%
    dplyr::rename(col = column_number, row = row_number) %>%
    dplyr::ungroup() %>%
    dplyr::select (-column_name, -project_id)

  messages

}



write_comment <- function (wb, author, sheet, message, col, row) {
  comment <- openxlsx::createComment(message, author = author, width= 1, height = 2)
  openxlsx::writeComment(wb = wb, sheet = sheet, col = col, row = row, comment =  comment)
  invisible(wb)
}
