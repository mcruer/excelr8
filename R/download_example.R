#' Download Example File to Working Directory
#'
#' Copies a sample workbook template 'workbook_template.xlsx' from the
#' package's `extdata` folder to the user's current working directory.
#'
#' The `get_workbook_template` function provides users with easy access to a
#' sample workbook template packaged with `excelr8`. This file can
#' be used as a basis for the user's work.
#'
#' @details
#' The example files are stored in the `extdata` directory of the
#' `excelr8` package. This function uses the `fs` package to handle
#' file operations.
#'
#' @examples
#' \dontrun{
#' # To copy the example files to your working directory
#' get_workbook_template()
#'
#' # Check if the files are available in the working directory
#' list.files(pattern = "xlsx")
#' }
#'
#' @export
get_workbook_template <- function() {
  # Get the paths to the files within the package
  template_path <- system.file("extdata", "workbook_template.xlsx", package = "excelr8")

  # Check if files exist
  if (!file.exists(template_path)) {
    stop("Example file not found in the package.")
  }

  # Use the fs package to copy files to the working directory
  fs::file_copy(template_path, "./workbook_template.xlsx", overwrite = TRUE)

  message("File 'workbook_template.xlsx' has been copied to the current working directory.")
}
